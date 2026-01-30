import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 현재 모드(development/production)에 맞는 .env 파일을 로드합니다.
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [react()],

    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },

    server: {
      // host: true로 설정하면 '0.0.0.0'으로 바인딩되어
      // 외부(모바일, 다른 PC)에서도 접속 가능합니다. (IP 하드코딩 불필요)
      host: true,
      port: 5173,

      // 개발 생산성을 위해 에러 오버레이는 켜두는 것이 정석입니다.
      // (너무 불편하면 다시 주석 해제하세요)
      // hmr: { overlay: false },

      proxy: {
        '/api': {
          // 1순위: .env 파일의 VITE_API_URL
          // 2순위: 로컬 백엔드 기본 주소 (localhost:8003)
          target: env.VITE_API_URL || 'http://localhost:8003',
          changeOrigin: true,
          secure: false,
        },
      },
    },
  };
});
