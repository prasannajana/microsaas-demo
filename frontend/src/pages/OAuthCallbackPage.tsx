import { useEffect, useRef, useState } from 'react';
import { Alert, AlertDescription, AlertIcon, Center, Spinner, Stack, Text } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';
import { GlassCard } from '../components/ui/GlassCard';
import { GradientButton } from '../components/ui/GradientButton';
import { MeshBackground } from '../components/ui/MeshBackground';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';
import { useAuth } from '../context/AuthContext';
import { getErrorMessage } from '../lib/errors';
import { NONCE_MISMATCH_ERROR, describeOAuthError } from '../lib/oauthErrors';
import { clearOAuthNonce, nonceMatches, peekOAuthNonce } from '../lib/oauthNonce';
import { parseOAuthFragment } from '../services/authService';

/** Remove tokens from the address bar and history without triggering a navigation. */
function clearFragment(): void {
  const { pathname, search } = window.location;
  window.history.replaceState(window.history.state, '', `${pathname}${search}`);
}

interface CallbackState {
  accessToken: string | null;
  refreshToken: string | null;
  initialError: string | null;
}

function readCallback(): CallbackState {
  const { accessToken, refreshToken, error, nonce } = parseOAuthFragment(window.location.hash);
  // Peek only: React StrictMode may run this initializer twice. The effect clears it.
  const expectedNonce = peekOAuthNonce();
  if (error) return { accessToken: null, refreshToken: null, initialError: describeOAuthError(error) };
  if (!accessToken || !refreshToken) {
    return {
      accessToken: null,
      refreshToken: null,
      initialError: 'No sign-in credentials were received. Please try again.',
    };
  }
  // Login-CSRF: only accept tokens from a flow this tab started.
  if (!nonceMatches(expectedNonce, nonce)) {
    return { accessToken: null, refreshToken: null, initialError: NONCE_MISMATCH_ERROR };
  }
  return { accessToken, refreshToken, initialError: null };
}

export default function OAuthCallbackPage() {
  const { setTokens } = useAuth();
  const navigate = useNavigate();
  // Read the fragment once, during the first render (before the effect clears it).
  const [callback] = useState<CallbackState>(readCallback);
  const [error, setError] = useState<string | null>(callback.initialError);
  // StrictMode runs effects twice in dev; tokens are single-use, so only handle once.
  const handledRef = useRef(false);

  useEffect(() => {
    if (handledRef.current) return;
    handledRef.current = true;
    clearFragment();
    clearOAuthNonce(); // single use, whatever the outcome

    const { accessToken, refreshToken } = callback;
    if (!accessToken || !refreshToken) return;

    setTokens(accessToken, refreshToken)
      .then(() => navigate('/dashboard', { replace: true }))
      .catch((err: unknown) => setError(getErrorMessage(err, 'Could not complete sign-in.')));
  }, [callback, navigate, setTokens]);

  return (
    <>
      <MeshBackground />
      <PageWrapper>
        <Center minH="80vh">
          <GlassCard hoverable={false} w="full" maxW="md" p={{ base: 6, md: 8 }}>
            {error ? (
              <Stack spacing={5}>
                <TextReveal text="Sign-in failed" size="lg" />
                <Alert status="error" borderRadius="xl">
                  <AlertIcon />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
                <GradientButton onClick={() => navigate('/login', { replace: true })} size="lg" w="full">
                  Back to sign in
                </GradientButton>
              </Stack>
            ) : (
              <Stack spacing={5} align="center" textAlign="center">
                <TextReveal text="Signing you in" size="lg" />
                <Spinner size="lg" color="brand.500" thickness="4px" />
                <Text color="text.muted">Completing Google sign-in…</Text>
              </Stack>
            )}
          </GlassCard>
        </Center>
      </PageWrapper>
    </>
  );
}
