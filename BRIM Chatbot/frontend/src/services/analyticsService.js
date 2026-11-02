import api from './api';

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function download(path, params, fallbackName) {
  const response = await api.get(path, {
    params: { ...params, format: 'csv' },
    responseType: 'blob',
    timeout: 60000,
  });
  const disposition = response.headers['content-disposition'] || '';
  const match = disposition.match(/filename="?([^";]+)"?/);
  triggerDownload(response.data, match ? match[1] : fallbackName);
}

export const analyticsService = {
  overview: (params) => api.get('/analytics/overview', { params }).then((r) => r.data),

  bot: (botId, params) =>
    api.get(`/analytics/bots/${botId}`, { params }).then((r) => r.data),

  report: (kind, params) => api.get(`/reports/${kind}`, { params }).then((r) => r.data),

  downloadCsv: (kind, params = {}) =>
    download(`/reports/${kind}`, params, `brim_${kind}.csv`),

  admin: {
    overview: (params) => api.get('/admin/overview', { params }).then((r) => r.data),
    users: (params) => api.get('/admin/users', { params }).then((r) => r.data),
    projects: (params) => api.get('/admin/projects', { params }).then((r) => r.data),
    bots: (params) => api.get('/admin/bots', { params }).then((r) => r.data),
    conversations: (params) => api.get('/admin/conversations', { params }).then((r) => r.data),
    leads: (params) => api.get('/admin/leads', { params }).then((r) => r.data),
    activity: (params) => api.get('/admin/activity', { params }).then((r) => r.data),
    downloadCsv: (kind, params = {}) =>
      download(`/admin/reports/${kind}`, params, `brim_platform_${kind}.csv`),
  },
};

export function rangeParams(days) {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - (days - 1));
  const iso = (date) => date.toISOString().slice(0, 10);
  return { start: iso(start), end: iso(end) };
}
