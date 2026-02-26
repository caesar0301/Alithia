import { useEffect, useRef, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { api } from '../api';

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

interface VerifyPageProps {
  onVerified: () => void;
}

export default function VerifyPage({ onVerified }: VerifyPageProps) {
  const [siteKey, setSiteKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const widgetRef = useRef<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Get the Turnstile site key
    api.getPublicConfig().then((cfg) => {
      if (!cfg.turnstile_enabled || !cfg.turnstile_site_key) {
        // If Turnstile is disabled, just verify directly
        onVerified();
        return;
      }
      setSiteKey(cfg.turnstile_site_key);
      setLoading(false);
    }).catch(() => {
      // If we can't get config, allow access
      onVerified();
    });

    return () => {
      if (widgetRef.current && window.turnstile) {
        window.turnstile.remove(widgetRef.current);
      }
    };
  }, [onVerified]);

  useEffect(() => {
    if (!siteKey || !window.turnstile) return;

    if (widgetRef.current) {
      window.turnstile.remove(widgetRef.current);
    }

    widgetRef.current = window.turnstile.render(containerRef.current!, {
      sitekey: siteKey,
      callback: handleVerify,
      'error-callback': () => {
        setError('Verification failed. Please try again.');
        setVerifying(false);
      },
      'timeout-callback': () => {
        setError('Verification timed out. Please try again.');
        setVerifying(false);
      },
    });
  }, [siteKey]);

  const handleVerify = async (token: string) => {
    setVerifying(true);
    setError('');

    try {
      const result = await api.verifyTurnstile(token);
      if (result.success) {
        onVerified();
      } else {
        setError(result.message || 'Verification failed. Please try again.');
        // Reset the widget for retry
        if (widgetRef.current && window.turnstile) {
          window.turnstile.reset(widgetRef.current);
        }
      }
    } catch (err) {
      setError('Verification failed. Please try again.');
    } finally {
      setVerifying(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-lg shadow-lg p-8">
          <div className="text-center mb-6">
            <div className="mx-auto w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center mb-4">
              <ShieldCheck className="w-6 h-6 text-indigo-600" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Verification Required</h1>
            <p className="text-gray-600 mt-2">
              Please complete the security check below to access the dashboard.
            </p>
          </div>

          <div className="flex justify-center mb-6">
            <div ref={containerRef}></div>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-600 text-center">{error}</p>
            </div>
          )}

          {verifying && (
            <div className="text-center">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-600 mx-auto"></div>
              <p className="text-sm text-gray-500 mt-2">Verifying...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
