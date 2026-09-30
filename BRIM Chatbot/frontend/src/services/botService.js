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
  }
};
