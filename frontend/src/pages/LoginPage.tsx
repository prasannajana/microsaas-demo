import { useCallback } from 'react';
import { Center, Divider, HStack, Link, Stack, Text } from '@chakra-ui/react';
import { Link as RouterLink, Navigate, useLocation } from 'react-router-dom';
import { GoogleLoginButton } from '../components/auth/GoogleLoginButton';
import { LoginForm } from '../components/auth/LoginForm';
import { GlassCard } from '../components/ui/GlassCard';
import { LoadingScreen } from '../components/ui/LoadingScreen';
import { MeshBackground } from '../components/ui/MeshBackground';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';
import { useAuth } from '../context/AuthContext';

const DEFAULT_REDIRECT = '/dashboard';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/** Resolve `location.state.from` (set by ProtectedRoute) to a safe in-app path. */
function getRedirectTarget(state: unknown): string {
  if (!isRecord(state)) return DEFAULT_REDIRECT;
  const from = state.from;
  let path: string | null = null;
  if (typeof from === 'string') {
    path = from;
  } else if (isRecord(from) && typeof from.pathname === 'string') {
    const search = typeof from.search === 'string' ? from.search : '';
    const hash = typeof from.hash === 'string' ? from.hash : '';
    path = `${from.pathname}${search}${hash}`;
  }
  if (!path || !path.startsWith('/') || path.startsWith('//') || path.startsWith('/login')) {
    return DEFAULT_REDIRECT;
  }
  return path;
}

export default function LoginPage() {
  const { user, isLoading, login } = useAuth();
  const location = useLocation();
  const redirectTo = getRedirectTarget(location.state);

  const handleLogin = useCallback((email: string, password: string) => login(email, password), [login]);

  if (isLoading) return <LoadingScreen />;
  if (user) return <Navigate to={redirectTo} replace />;

  return (
    <>
      <MeshBackground />
      <PageWrapper>
        <Center minH="80vh">
          <GlassCard hoverable={false} w="full" maxW="md" p={{ base: 6, md: 8 }}>
            <Stack spacing={6}>
              <Stack spacing={2}>
                <TextReveal text="Welcome back" size="xl" />
                <Text color="text.muted">Sign in to keep your projects ship-ready.</Text>
              </Stack>
              <LoginForm onSubmit={handleLogin} />
              <HStack>
                <Divider />
                <Text fontSize="sm" color="text.muted" whiteSpace="nowrap">
                  or
                </Text>
                <Divider />
              </HStack>
              <GoogleLoginButton />
              <Stack spacing={1} fontSize="sm" textAlign="center">
                <Link as={RouterLink} to="/forgot-password" color="brand.600" fontWeight="medium">
                  Forgot your password?
                </Link>
                <Text color="text.muted">
                  New here?{' '}
                  <Link as={RouterLink} to="/register" color="brand.600" fontWeight="semibold">
                    Create an account
                  </Link>
                </Text>
              </Stack>
            </Stack>
          </GlassCard>
        </Center>
      </PageWrapper>
    </>
  );
}
