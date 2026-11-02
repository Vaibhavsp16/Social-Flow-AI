import api from './api';

export const knowledgeService = {
  async getBotKnowledge(botId) {
    const response = await api.get(`/bots/${botId}/knowledge`);
    return response.data;
  },

  async uploadFile(botId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post(`/bots/${botId}/knowledge/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 180000,
    });
    return response.data;
  },

  async addWebsite(botId, { url, name, maxPages = 1 }) {
    // A multi-page crawl fetches and embeds several pages, so it needs a longer ceiling.
    const response = await api.post(
      `/bots/${botId}/knowledge/website`,
      { url, name, max_pages: maxPages },
      { timeout: 180000 }
    );
    return response.data;
  },

  async addSocialLink(botId, { url, platform, name, caption }) {
    const response = await api.post(`/bots/${botId}/knowledge/social`, {
      url,
      platform,
      name,
      caption: caption || undefined,
    });
    return response.data;
  },

  async addInstruction(botId, data) {
    const response = await api.post(`/bots/${botId}/knowledge/instruction`, data);
    return response.data;
  },

  async updateKnowledgeSource(sourceId, data) {
    const response = await api.put(`/knowledge/${sourceId}`, data);
    return response.data;
  },

  async deleteKnowledgeSource(sourceId) {
    const response = await api.delete(`/knowledge/${sourceId}`);
    return response.data;
  },

  async getSampleDocuments() {
    const response = await api.get('/knowledge/samples');
    return response.data;
  },

  async seedSampleDocument(botId, sampleKey) {
    const response = await api.post(`/bots/${botId}/knowledge/seed-sample`, { sample_key: sampleKey });
    return response.data;
  },

  // The eight BRIM industries (brim.co.in/industry) and their ready-to-index knowledge packs.
  async getIndustryPacks() {
    const response = await api.get('/knowledge/industry-packs');
    return response.data;
  },

  async seedIndustryPack(botId, industryKey) {
    const response = await api.post(
      `/bots/${botId}/knowledge/seed-industry`,
      { industry_key: industryKey },
      { timeout: 180000 }
    );
    return response.data;
  },
};
