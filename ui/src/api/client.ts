// ui/src/api/client.ts
import axios from 'axios';

// 브라우저는 동일 출처 API 경로를 사용하고, 개발 환경에서는 Vite가 실제 API로 프록시합니다.
const API_BASE_URL = '/api/v1';

export const axiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error(
      '🔥 [API Error]',
      error.response?.data?.detail || error.message,
    );
    return Promise.reject(error);
  },
);
