import os
import json
import logging
import time
from typing import List, Optional, Dict, Any, Tuple
from app.models.bot import Bot
from app.models.knowledge_chunk import KnowledgeChunk
from app.schemas.chat import ChatMessage, SourceCitation

logger = logging.getLogger(__name__)

GROUNDED_REFUSAL_MESSAGE = (
    "I do not have enough information in my knowledge base to answer this question accurately. "
    "Please contact our support team or reach out to a human advisor for further assistance."
)

class LLMService:
    """
    Centralized LLM Service abstraction with support for:
    - System prompt & persona
    - Bot-specific personality & instructions
    - Grounded retrieved context injection
    - Multi-turn conversation context
    - Model configuration (temperature, max_tokens, retries)
    - Fallback grounded synthesizer for zero-cost offline & testing environments
    - Resilient error handling and exponential backoff retry logic
    """

    @classmethod
    def get_openai_client(cls):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.startswith("sk-placeholder") or api_key == "mock":
            return None
        try:
            from openai import OpenAI
            return OpenAI(api_key=api_key)
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {e}")
            return None

    @classmethod
    def build_system_prompt(
        cls,
        bot: Bot,
        retrieved_chunks: List[Tuple[KnowledgeChunk, float]],
        conversation_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Assemble a strict, grounded system prompt with bot persona, conversation state,
        and retrieved context.
        """
        prompt_parts = [
            f"You are {bot.name}, a helpful AI assistant for this business.",
            f"Personality: {bot.personality or 'Friendly & professional'}.",
            f"Language: {bot.language or 'English'}.",
            "",
            "HOW TO TALK:",
            "- Use simple, clear words. Aim for 5th-grade English.",
            "- Keep answers short — 2 to 4 sentences when possible.",
            "- Do NOT use jargon, long paragraphs, or complicated words.",
            "- Be friendly and warm. The user is a real person looking for help.",
            "",
            "RULES FOR ANSWERING:",
            "1. Only use facts from the KNOWLEDGE BASE below. Do NOT guess or make up details.",
            "2. If the knowledge base does not have the answer, say: 'I don't have that info right now. Would you like me to connect you with someone from our team?'",
            "3. Do NOT repeat questions the user already answered. Use the CONVERSATION STATE below.",
            "4. If the user wants a human, say you will connect them right away.",
        ]

        # Inject conversation state so LLM doesn't re-ask known info
        if conversation_state:
            state_lines = []
            if conversation_state.get("intent"):
                state_lines.append(f"  - Intent: {conversation_state['intent']}")
            if conversation_state.get("location"):
                state_lines.append(f"  - Location preference: {conversation_state['location']}")
            if conversation_state.get("bhk"):
                state_lines.append(f"  - BHK requirement: {conversation_state['bhk']} BHK")
            if conversation_state.get("budget_max"):
                b = conversation_state["budget_max"]
                if b >= 10_000_000:
                    state_lines.append(f"  - Budget: up to ₹{b/10_000_000:.1f} Cr")
                else:
                    state_lines.append(f"  - Budget: up to ₹{b/100_000:.0f} Lakhs")
            if conversation_state.get("amenities"):
                state_lines.append(f"  - Amenities wanted: {', '.join(conversation_state['amenities'])}")
            if state_lines:
                prompt_parts.append("")
                prompt_parts.append("CONVERSATION STATE (already known — do NOT ask again):")
                prompt_parts.extend(state_lines)

        prompt_parts += [
            "",
            "--- KNOWLEDGE BASE ---",
        ]

        if not retrieved_chunks:
            prompt_parts.append("[No matching records found for this question.]")
        else:
            for idx, (chunk, score) in enumerate(retrieved_chunks, 1):
                page_info = f", Section: {chunk.page_number}" if chunk.page_number else ""
                url_info = f", URL: {chunk.source_url}" if chunk.source_url else ""
                prompt_parts.append(
                    f"[Source #{idx}: {chunk.source_name}{page_info}{url_info}]\n"
                    f"{chunk.content}\n"
                )

        prompt_parts.append("--- END OF KNOWLEDGE BASE ---")
        return "\n".join(prompt_parts)

    @classmethod
    def generate_grounded_response(
        cls,
        bot: Bot,
        retrieved_chunks: List[Tuple[KnowledgeChunk, float]],
        user_query: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        conversation_state: Optional[Dict[str, Any]] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.25,
        max_tokens: int = 512,
        max_retries: int = 3,
    ) -> str:
        """
        Execute LLM completion with retries, or perform grounded local synthesis if API key is not configured.
        """
        # If no knowledge chunks were found or similarity is insufficient, decline politely
        if not retrieved_chunks:
            return GROUNDED_REFUSAL_MESSAGE

        client = cls.get_openai_client()

        if client:
            system_prompt = cls.build_system_prompt(bot, retrieved_chunks, conversation_state)
            messages = [{"role": "system", "content": system_prompt}]

            # Add recent conversation turns
            if conversation_history:
                for msg in conversation_history[-6:]:
                    if msg.role in ["user", "assistant", "system"]:
                        messages.append({"role": msg.role, "content": msg.content})

            messages.append({"role": "user", "content": user_query})

            # Retry loop with exponential backoff
            for attempt in range(1, max_retries + 1):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    reply = response.choices[0].message.content.strip()
                    if reply:
                        return reply
                except Exception as e:
                    logger.warning(f"LLM generation attempt {attempt}/{max_retries} failed: {e}")
                    if attempt < max_retries:
                        time.sleep(2 ** attempt * 0.5)
                    else:
                        logger.error(f"All LLM retries failed. Falling back to grounded context synthesis.")

        # Grounded Local Synthesizer Fallback (Deterministic, hallucination-free, zero-cost)
        return cls._local_grounded_synthesis(bot, retrieved_chunks, user_query)

    @classmethod
    def _local_grounded_synthesis(
        cls,
        bot: Bot,
        retrieved_chunks: List[Tuple[KnowledgeChunk, float]],
        user_query: str
    ) -> str:
        """
        Deterministic local fallback synthesis when external LLM APIs are unreachable or not configured.
        Extracts relevant facts strictly from the top matching knowledge chunks without hallucination.
        """
        if not retrieved_chunks:
            return GROUNDED_REFUSAL_MESSAGE

        top_chunk, top_score = retrieved_chunks[0]

        # Check if query terms share meaningful semantic overlap with top chunk
        query_words = set(w.lower() for w in user_query.split() if len(w) > 3)
        chunk_text_lower = top_chunk.content.lower()

        # If there is very weak keyword overlap despite vector distance, trigger safety refusal
        has_overlap = any(word in chunk_text_lower for word in query_words)
        if not has_overlap and top_score < 0.35:
            return GROUNDED_REFUSAL_MESSAGE

        # Formulate grounded direct response using retrieved chunk content
        cleaned_content = top_chunk.content.strip()
        lines = [line.strip() for line in cleaned_content.split("\n") if line.strip()]
        
        # Present direct grounded information
        source_label = f"Based on {top_chunk.source_name}"
        if top_chunk.page_number:
            source_label += f" ({top_chunk.page_number})"
        
        if len(lines) <= 4:
            body = "\n".join(lines)
        else:
            body = "\n".join(lines[:4])

        return f"{source_label}:\n\n{body}"
