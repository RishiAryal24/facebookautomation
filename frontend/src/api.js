import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
let accessToken = null;
let refreshPromise = null;

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

const getErrorMessage = (detail) => {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (!item || typeof item !== 'object') return '';
        const location = Array.isArray(item.loc)
          ? item.loc.filter((part) => part !== 'body').join('.')
          : '';
        const message = typeof item.msg === 'string' ? item.msg : 'Invalid value';
        return location ? `${location}: ${message}` : message;
      })
      .filter(Boolean)
      .join('; ');
  }
  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string') return detail.message;
    if (typeof detail.msg === 'string') return detail.msg;
  }
  return null;
};

export const setAccessToken = (token) => {
  accessToken = token;
};

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const request = error.config;
    const isAuthRequest = /\/auth\/(login|refresh|logout)$/.test(request?.url || '');
    if (error.response?.status === 401 && request && !request._authRetry && !isAuthRequest) {
      request._authRetry = true;
      try {
        if (!refreshPromise) {
          refreshPromise = axios
            .post(`${API_BASE_URL}/auth/refresh`, null, { withCredentials: true })
            .then((response) => {
              setAccessToken(response.data.access_token);
              return response.data.access_token;
            })
            .finally(() => {
              refreshPromise = null;
            });
        }
        const renewedToken = await refreshPromise;
        request.headers.Authorization = `Bearer ${renewedToken}`;
        return api(request);
      } catch {
        setAccessToken(null);
        window.dispatchEvent(new Event('auth:expired'));
      }
    }

    const message =
      getErrorMessage(error.response?.data?.detail) ||
      error.message ||
      'An error occurred';
    const apiError = new Error(message);
    const detail = error.response?.data?.detail;
    if (detail && typeof detail === 'object') {
      apiError.metaError = detail.meta_error || null;
      apiError.validationStatus = detail.status || null;
    }
    return Promise.reject(apiError);
  }
);

export default api;
