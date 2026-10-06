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
        # Greetings are answered before the knowledge check, so saying "hi" to a bot that has
        # no (or unmatched) knowledge never produces a refusal.
        greeting_reply = cls._greeting_reply(bot, user_query, retrieved_chunks)
        if greeting_reply:
            return greeting_reply

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

            # Try LLM completion
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
                    err_str = str(e).lower()
                    if "insufficient_quota" in err_str or "credit_balance_exhausted" in err_str or "quota" in err_str:
                        logger.info("OpenAI quota exhausted. Seamlessly utilizing grounded synthesis engine.")
                        break
                    logger.warning(f"LLM generation attempt {attempt}/{max_retries} failed: {e}")
                    if attempt < max_retries:
                        time.sleep(1.0)
                    else:
                        logger.info("Falling back to grounded context synthesis.")

        # Grounded Local Synthesizer Fallback (Deterministic, hallucination-free, zero-cost)
        return cls._local_grounded_synthesis(bot, retrieved_chunks, user_query)

    GREETING_WORDS = {
        "hi", "hii", "hello", "hey", "yo", "greetings", "morning", "afternoon", "evening",
        "thanks", "thank", "bye", "goodbye", "help",
    }

    @classmethod
    def _greeting_reply(
        cls,
        bot: Bot,
        user_query: str,
        retrieved_chunks: Optional[List[Tuple[KnowledgeChunk, float]]] = None,
    ) -> Optional[str]:
        """
        Warm, bot-specific reply for a short greeting or thanks. Returns None when the message
        is a real question, so it is never mistaken for one.
        """
        import re

        words = set(re.findall(r"[a-z0-9]+", user_query.lower()))
        if not words or len(words) > 4 or not (words & cls.GREETING_WORDS):
            return None

        welcome = bot.welcome_message or f"Hello! 👋 I'm {bot.name}. How can I assist you today?"
        if retrieved_chunks:
            return (
                f"{welcome}\n\nI have information loaded from our knowledge base "
                f"({retrieved_chunks[0][0].source_name}). Feel free to ask any questions!"
            )
        return welcome

    @classmethod
    def _local_grounded_synthesis(
        cls,
        bot: Bot,
        retrieved_chunks: List[Tuple[KnowledgeChunk, float]],
        user_query: str
    ) -> str:
        """
        Deterministic local fallback synthesis when external LLM APIs are unreachable or not configured.
        Extracts relevant facts strictly from the top matching knowledge chunks with 5th-grade clarity.
        """
        import re

        clean_query = re.sub(r'[^a-zA-Z0-9\s]', ' ', user_query.lower()).strip()
        query_words = set(w for w in clean_query.split() if len(w) > 1)

        if not retrieved_chunks:
            return GROUNDED_REFUSAL_MESSAGE

        top_chunk, top_score = retrieved_chunks[0]
        chunk_text = top_chunk.content.strip()
        chunk_text_lower = chunk_text.lower()

        # Stop words to filter out noise
        stop_words = {
            "what", "which", "where", "when", "how", "who", "why", "the", "and", "for",
            "with", "about", "your", "this", "that", "tell", "have", "does", "give", "info",
            "information", "details", "explain", "describe", "please", "can", "you", "are",
            "his", "her", "their", "our", "him", "she", "any", "some", "all"
        }
        content_query_words = {w for w in query_words if len(w) > 2 and w not in stop_words}

        # Check keyword presence across all retrieved chunks
        all_chunks_text = " ".join([c.content.lower() for c, _ in retrieved_chunks])
        has_overlap = any(w in all_chunks_text for w in content_query_words) if content_query_words else True

        # Broad "what do you know about this business" questions carry no specific term to match
        # on, so they are answered from the retrieved content instead of being refused.
        overview_terms = {
            "information", "info", "about", "business", "company", "service", "services",
            "offer", "offers", "know", "knowledge", "overview", "summary", "details",
            "available", "help", "assist", "product", "products",
        }
        is_overview_query = bool(query_words & overview_terms)

        # Safety check: if the user asked something completely off-topic with no overlap,
        # refuse with the single canonical refusal message instead of inventing an answer.
        if content_query_words and not has_overlap and not is_overview_query:
            return GROUNDED_REFUSAL_MESSAGE

        # 2. Extract most relevant sentences or paragraphs from retrieved chunks
        paragraphs = [p.strip() for p in chunk_text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [p.strip() for p in chunk_text.split("\n") if p.strip()]

        selected_parts = []
        if content_query_words:
            # Score paragraphs by query overlap
            for p in paragraphs:
                p_lower = p.lower()
                overlap_count = sum(1 for w in content_query_words if w in p_lower)
                if overlap_count > 0:
                    selected_parts.append((p, overlap_count))
            selected_parts.sort(key=lambda x: x[1], reverse=True)

        if selected_parts:
            chosen_text = "\n\n".join(p[0] for p in selected_parts[:2])
        else:
            # Fall back to top paragraphs
            chosen_text = "\n\n".join(paragraphs[:3]) if len(paragraphs) >= 3 else chunk_text

        body = cls._humanize(chosen_text)

        source_info = top_chunk.source_name
        if top_chunk.page_number:
            source_info += f" ({top_chunk.page_number})"

        return f"Here is what I found in our knowledge base:\n\n{body}\n\n*(Source: {source_info})*"

    @staticmethod
    def _humanize(text: str) -> str:
        """
        Strip document markup (markdown headings, bold markers, list syntax) so the answer
        reads as prose instead of a raw chunk dump. The facts are untouched.
        """
        import re

        cleaned = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
        cleaned = cleaned.replace("**", "").replace("__", "")
        cleaned = re.sub(r"^\s*[-*]\s+", "• ", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()
