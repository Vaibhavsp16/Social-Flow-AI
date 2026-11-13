import api from './api';

export const chatService = {
  // ── Legacy single-shot QA (kept for backward compat) ──────────────────────
  sendMessage: async (botId, message, conversationHistory = []) => {
    const response = await api.post(`/bots/${botId}/chat`, {
      message,
      conversation_history: conversationHistory,
    });
    return response.data;
  },

  sendPublicMessage: async (slug, message, conversationHistory = []) => {
    const response = await api.post(`/public/bots/${slug}/chat`, {
      message,
      conversation_history: conversationHistory,
    });
    return response.data;
  },

  // ── Conversation session management ───────────────────────────────────────
  createConversation: async (botId, sessionId = null, context = {}) => {
    const response = await api.post('/conversations', {
      bot_id: botId,
      session_id: sessionId,
      ...context,
    });
    return response.data;
  },

  createPublicConversation: async (slug, payload = {}) => {
    const response = await api.post(`/public/conversations/${slug}`, payload);
    return response.data;
  },

  getConversation: async (conversationId) => {
    const response = await api.get(`/conversations/${conversationId}`);
    return response.data;
  },

  getPublicConversation: async (conversationId) => {
    const response = await api.get(`/public/conversations/${conversationId}`);
    return response.data;
  },

  listConversations: async (botId, limit = 50, visitorId = null) => {
    const params = { limit };
    if (visitorId) params.visitor_id = visitorId;
    const response = await api.get(`/bots/${botId}/conversations`, { params });
    return response.data;
  },

  listAllConversations: async (botId = null, limit = 50) => {
    const params = { limit };
    if (botId) params.bot_id = botId;
    const response = await api.get('/conversations', { params });
    return response.data;
  },

  // ── Send message in a conversation ────────────────────────────────────────
  sendConversationMessage: async (conversationId, message, language = null) => {
    const payload = { message };
    if (language) payload.language = language;
    const response = await api.post(`/conversations/${conversationId}/messages`, payload);
    return response.data;
  },

  // Persist a reply produced by the optional browser-side Puter client.
  updateMessage: async (messageId, content) => {
    const response = await api.patch(`/messages/${messageId}`, { content });
    return response.data;
  },

  sendPublicConversationMessage: async (conversationId, message, language = null) => {
    const payload = { message };
    if (language) payload.language = language;
    const response = await api.post(`/public/conversations/${conversationId}/messages`, payload);
    return response.data;
  },

  // ── Proactive contact ─────────────────────────────────────────────────────
  /** Ask the bot to re-engage a visitor who went quiet. Fires at most once per conversation. */
  nudge: async (conversationId) => {
    const response = await api.post(`/public/conversations/${conversationId}/nudge`, {
      kind: 'idle',
    });
    return response.data;
  },

  submitContact: async (conversationId, payload, authenticated = false) => {
    const path = authenticated
      ? `/conversations/${conversationId}/contact`
      : `/public/conversations/${conversationId}/contact`;
    const response = await api.post(path, payload);
    return response.data;
  },

  // ── End a conversation ────────────────────────────────────────────────────
  endConversation: async (conversationId) => {
    const response = await api.patch(`/conversations/${conversationId}/end`);
    return response.data;
  },
};

export default chatService;
