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
  createConversation: async (botId, sessionId = null) => {
    const response = await api.post('/conversations', {
      bot_id: botId,
      session_id: sessionId,
    });
    return response.data;
  },

  createPublicConversation: async (slug) => {
    const response = await api.post(`/public/conversations/${slug}`);
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

  listConversations: async (botId, limit = 50) => {
    const response = await api.get(`/bots/${botId}/conversations`, {
      params: { limit },
    });
    return response.data;
  },

  listAllConversations: async (botId = null, limit = 50) => {
    const params = { limit };
    if (botId) params.bot_id = botId;
    const response = await api.get('/conversations', { params });
    return response.data;
  },

  // ── Send message in a conversation ────────────────────────────────────────
  sendConversationMessage: async (conversationId, message) => {
    const response = await api.post(`/conversations/${conversationId}/messages`, {
      message,
    });
    return response.data;
  },

  sendPublicConversationMessage: async (conversationId, message) => {
    const response = await api.post(`/public/conversations/${conversationId}/messages`, {
      message,
    });
    return response.data;
  },

  // ── End a conversation ────────────────────────────────────────────────────
  endConversation: async (conversationId) => {
    const response = await api.patch(`/conversations/${conversationId}/end`);
    return response.data;
  },
};

export default chatService;
