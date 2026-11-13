import api from './api';

export const botService = {
  async getBots(projectId = null) {
    const url = projectId ? `/bots?project_id=${projectId}` : '/bots';
    const response = await api.get(url);
    return response.data;
  },

  async getBot(id) {
    const response = await api.get(`/bots/${id}`);
    return response.data;
  },

  async createBot(data) {
    const response = await api.post('/bots', data);
    return response.data;
  },

  async updateBot(id, data) {
    const response = await api.put(`/bots/${id}`, data);
    return response.data;
  },

  async deleteBot(id) {
    const response = await api.delete(`/bots/${id}`);
    return response.data;
  },

  // ── Public surface (no auth) ──────────────────────────────────────────────
  async getPublicBot(slug) {
    const response = await api.get(`/public/bots/${encodeURIComponent(slug)}`);
    return response.data;
  },

  async getEmbedSnippet(slug) {
    const response = await api.get(`/public/bots/${encodeURIComponent(slug)}/embed-snippet`);
    return response.data;
  },

  // ── Custom domain (owner) ─────────────────────────────────────────────────
  async getDomain(botId) {
    const response = await api.get(`/bots/${botId}/domain`);
    return response.data;
  },

  async setDomain(botId, domain) {
    const response = await api.put(`/bots/${botId}/domain`, { domain });
    return response.data;
  },

  async verifyDomain(botId) {
    const response = await api.post(`/bots/${botId}/domain/verify`);
    return response.data;
  },

  // ── Leads and meetings (owner) ────────────────────────────────────────────
  async getLeads(botId, limit = 100) {
    const response = await api.get(`/bots/${botId}/leads`, { params: { limit } });
    return response.data;
  },

  async updateLeadStatus(leadId, status) {
    const response = await api.patch(`/leads/${leadId}`, { status });
    return response.data;
  },

  async getMeetings(botId, limit = 100) {
    const response = await api.get(`/bots/${botId}/meetings`, { params: { limit } });
    return response.data;
  },

  async updateMeetingStatus(meetingId, status) {
    const response = await api.patch(`/meetings/${meetingId}`, { status });
    return response.data;
  },

  /** Download the leads CSV in the browser (auth header included by the axios instance). */
  async downloadLeadsCsv(botId, params = {}) {
    const response = await api.get(`/bots/${botId}/leads.csv`, {
      params,
      responseType: 'blob',
    });
    const disposition = response.headers['content-disposition'] || '';
    const match = disposition.match(/filename="?([^";]+)"?/);
    const url = URL.createObjectURL(response.data);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = match ? match[1] : `leads_${botId}.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  },
};

export default botService;
