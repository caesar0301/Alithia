import { useEffect, useRef, useState, useCallback } from 'react';
import { api } from '../api';

const TOKEN_TIMEOUT_MS = 8000;

declare global {
  interface Window {
    turnstile?: {
      render: (container: HTMLElement, opts: Record<string, unknown>) => string;
      reset: (widgetId: string) => void;
      getResponse: (widgetId: string) => string | undefined;
      remove: (widgetId: string) => void;
    };
  }
}

/**
 * Manages a hidden Cloudflare Turnstile widget.
 * Returns `getToken` to obtain a fresh token before each protected request.
 * When Turnstile is disabled on the server, `getToken` returns null.
 * When the widget errors or times out, `getToken` returns null so callers
 * proceed without a token (the backend will decide whether to reject).
 */
export function useTurnstile() {
  const [enabled, setEnabled] = useState(false);
  const [siteKey, setSiteKey] = useState('');
  const widgetIdRef = useRef<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const tokenRef = useRef<string | null>(null);
  const resolveRef = useRef<((token: string | null) => void) | null>(null);

  useEffect(() => {
    api.getPublicConfig().then((cfg) => {
      setEnabled(cfg.turnstile_enabled);
      setSiteKey(cfg.turnstile_site_key);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!enabled || !siteKey) return;

    const mount = () => {
      if (!window.turnstile || widgetIdRef.current) return;

      let container = containerRef.current;
      if (!container) {
        container = document.createElement('div');
        container.style.position = 'fixed';
        container.style.bottom = '-200px';
        container.style.left = '-200px';
        container.style.opacity = '0';
        container.style.pointerEvents = 'none';
        document.body.appendChild(container);
        containerRef.current = container;
      }

      widgetIdRef.current = window.turnstile.render(container, {
        sitekey: siteKey,
        callback: (token: string) => {
          tokenRef.current = token;
          resolveRef.current?.(token);
          resolveRef.current = null;
        },
        'error-callback': () => {
          resolveRef.current?.(null);
          resolveRef.current = null;
        },
        'timeout-callback': () => {
          resolveRef.current?.(null);
          resolveRef.current = null;
        },
      });
    };

    if (window.turnstile) {
      mount();
    } else {
      const interval = setInterval(() => {
        if (window.turnstile) {
          clearInterval(interval);
          mount();
        }
      }, 200);
      return () => clearInterval(interval);
    }
  }, [enabled, siteKey]);

  const getToken = useCallback(async (): Promise<string | null> => {
    if (!enabled) return null;

    if (tokenRef.current) {
      const t = tokenRef.current;
      tokenRef.current = null;
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.reset(widgetIdRef.current);
      }
      return t;
    }

    // Race the widget callback against a timeout so callers never hang
    return new Promise<string | null>((resolve) => {
      const timer = setTimeout(() => {
        resolveRef.current = null;
        resolve(null);
      }, TOKEN_TIMEOUT_MS);

      resolveRef.current = (token) => {
        clearTimeout(timer);
        resolve(token);
      };

      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.reset(widgetIdRef.current);
      }
    });
  }, [enabled]);

  return { enabled, getToken };
}
