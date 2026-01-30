// ui/src/api/client.ts
import axios from 'axios';

// ✅ [원복] 복잡하게 IP 따라가지 말고, 그냥 무조건 로컬로 쏘게 고정합니다.
const API_BASE_URL = 'http://127.0.0.1:8003/api/v1';

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
