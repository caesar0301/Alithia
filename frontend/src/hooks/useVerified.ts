import { useState, useEffect, useCallback } from 'react';
import { api } from '../api';

const VERIFIED_KEY = 'alithia_turnstile_verified';
const SESSION_VERIFIED_KEY = 'alithia_session_verified';

/**
 * Manages Turnstile verification state for the frontend.
 * - If Turnstile is disabled on the server, always returns verified=true
 * - Uses sessionStorage to persist verification within a browser session
 * - Provides a way to clear verification state
 */
export function useVerified() {
  const [verified, setVerified] = useState<boolean | null>(null);
  const [turnstileEnabled, setTurnstileEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    // Check if Turnstile is enabled on the server
    api.getPublicConfig().then((cfg) => {
      setTurnstileEnabled(cfg.turnstile_enabled);
      
      // If Turnstile is disabled, always allow access
      if (!cfg.turnstile_enabled) {
        setVerified(true);
        return;
      }
      
      // Check if already verified in this session
      const sessionVerified = sessionStorage.getItem(SESSION_VERIFIED_KEY);
      if (sessionVerified === 'true') {
        setVerified(true);
      } else {
        setVerified(false);
      }
    }).catch(() => {
      // If we can't get config, assume Turnstile is disabled
      setTurnstileEnabled(false);
      setVerified(true);
    });
  }, []);

  const markVerified = useCallback(() => {
    sessionStorage.setItem(SESSION_VERIFIED_KEY, 'true');
    setVerified(true);
  }, []);

  const clearVerified = useCallback(() => {
    sessionStorage.removeItem(SESSION_VERIFIED_KEY);
    localStorage.removeItem(VERIFIED_KEY);
    setVerified(false);
  }, []);

  return {
    verified,
    turnstileEnabled,
    markVerified,
    clearVerified,
  };
}
