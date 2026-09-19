import { apiClient } from './client';

// Auth API
export const authApi = {
  login: (credentials) => {
    return apiClient.post('/auth/login', {
      email: credentials.email,
      password: credentials.password
    });
  },
  me: () => apiClient.get('/users/me'),
};

// Dashboard / System Metrics API
export const metricsApi = {
  getSystemHealth: () => apiClient.get('/health'),
  getTrainingRounds: () => apiClient.get('/training/rounds?limit=10'),
  getPredictionStats: () => apiClient.get('/analytics/predictions/stats'),
};

// Patients API
export const patientsApi = {
  list: () => apiClient.get('/patients'),
  get: (id) => apiClient.get(`/patients/${id}`),
  create: (data) => apiClient.post('/patients', data),
  delete: (id) => apiClient.delete(`/patients/${id}`),
};

// Predictions API
export const predictionsApi = {
  list: () => apiClient.get('/predictions'),
  get: (id) => apiClient.get(`/predictions/${id}`),
  create: (data) => apiClient.post('/predictions', data),
  delete: (id) => apiClient.delete(`/predictions/${id}`),
};

// XAI & Reports API
export const xaiApi = {
  generate: (predictionId) => apiClient.post(`/xai/reports/${predictionId}`, {}),
  getByPrediction: (predictionId) => apiClient.get(`/xai/predictions/${predictionId}`),
  downloadPdfBlob: (predictionId) => apiClient.get(`/reports/predictions/${predictionId}/pdf`, { responseType: 'blob' }),
  downloadPdfUrl: (predictionId) => `${apiClient.defaults.baseURL}/reports/predictions/${predictionId}/pdf`,
};

// Analytics API
export const analyticsApi = {
  getFLReport: () => apiClient.get('/analytics/fl/report'),
  getComparison: () => apiClient.get('/analytics/comparison'),
  getNodes: () => apiClient.get('/training/nodes'),
  checkFairness: (payload) => apiClient.post('/analytics/fairness', payload),
};
