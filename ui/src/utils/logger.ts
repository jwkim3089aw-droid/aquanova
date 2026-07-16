// ui/src/utils/logger.ts
const IS_DEV = import.meta.env.DEV;

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

class FrontendLogger {
  private formatMessage(level: LogLevel, message: string) {
    const time = new Date().toLocaleTimeString();
    return `[${time}] [${level}] ${message}`;
  }

  // 서버로 로그를 전송하는 헬퍼 함수
  private async sendToServer(level: LogLevel, message: string, data?: any) {
    // 개발 중에도 테스트해보고 싶다면 아래 줄을 임시로 주석 처리하세요.
    if (IS_DEV) return;

    try {
      const apiUrl = String(
        (import.meta as any).env.VITE_API_URL || '',
      ).replace(/\/+$/, '');
      const payload = {
        level,
        message,
        data:
          data instanceof Error
            ? { message: data.message, stack: data.stack }
            : data,
        url: window.location.href,
      };

      await fetch(`${apiUrl}/api/v1/logs/ui`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (e) {
      console.error('서버로 로그 전송 실패:', e);
    }
  }

  debug(message: string, data?: any) {
    if (!IS_DEV) return;
    console.debug(
      `%c${this.formatMessage('DEBUG', message)}`,
      'color: #9E9E9E; font-weight: bold;',
      data !== undefined ? data : '',
    );
  }

  info(message: string, data?: any) {
    if (!IS_DEV) return;
    console.info(
      `%c${this.formatMessage('INFO', message)}`,
      'color: #2196F3; font-weight: bold;',
      data !== undefined ? data : '',
    );
  }

  warn(message: string, data?: any) {
    console.warn(
      `%c${this.formatMessage('WARN', message)}`,
      'color: #FF9800; font-weight: bold;',
      data !== undefined ? data : '',
    );
    this.sendToServer('WARN', message, data);
  }

  error(message: string, error?: any) {
    console.error(
      `%c${this.formatMessage('ERROR', message)}`,
      'color: #F44336; font-weight: bold;',
      error !== undefined ? error : '',
    );
    this.sendToServer('ERROR', message, error);
  }
}

export const logger = new FrontendLogger();
