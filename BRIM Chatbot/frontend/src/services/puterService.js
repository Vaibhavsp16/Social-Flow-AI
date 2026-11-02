/**
 * Optional LLM provider: Puter.js.
 *
 * The backend owns retrieval, citations and conversation state. When the server has no LLM
 * configured it returns a `llm_prompt` containing the grounded context; this module sends that
 * prompt to Puter and the polished answer is persisted back through the API. Enable it with
 * VITE_USE_PUTER=true in frontend/.env — without that flag (or without a Puter session) the
 * server's deterministic answer is used unchanged.
 */
const ENABLED = String(import.meta.env.VITE_USE_PUTER || '').toLowerCase() === 'true';

function extractText(result) {
  if (!result) return '';
  if (typeof result === 'string') return result;
  if (typeof result.text === 'string') return result.text;
  const content = result?.message?.content;
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content.map((part) => (typeof part === 'string' ? part : part?.text || '')).join('');
  }
  return '';
}

export const puterService = {
  enabled: ENABLED,

  /**
   * Ask Puter for a grounded answer. Returns null on any failure so the caller keeps the
   * server answer rather than surfacing an error to the visitor.
   */
  async complete(prompt, { model = 'gpt-4o-mini' } = {}) {
    if (!ENABLED || !prompt) return null;
    try {
      // Loaded on demand so the SDK never ships in the default bundle.
      const { puter } = await import('@heyputer/puter.js');
      const reply = await puter.ai.chat(prompt, { model });
      const text = extractText(reply).trim();
      return text || null;
    } catch (error) {
      console.warn('[puter] request failed, keeping the server answer:', error);
      return null;
    }
  },
};
