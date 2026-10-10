import { useCallback, useState } from 'react';
import { Center, Divider, HStack, Link, Stack, Text } from '@chakra-ui/react';
import { Link as RouterLink, Navigate } from 'react-router-dom';
import { GoogleLoginButton } from '../components/auth/GoogleLoginButton';
import { RegisterForm, type RegisterValues } from '../components/auth/RegisterForm';
import { GlassCard } from '../components/ui/GlassCard';
import { LoadingScreen } from '../components/ui/LoadingScreen';
import { MeshBackground } from '../components/ui/MeshBackground';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';
import { useAuth } from '../context/AuthContext';

/** After a fresh sign-up, nudge the user straight to adding their first project. */
const FIRST_RUN_REDIRECT = '/projects/new';
const DEFAULT_REDIRECT = '/dashboard';

export default function RegisterPage() {
  const { user, isLoading, register } = useAuth();
  const [justRegistered, setJustRegistered] = useState(false);

  const handleRegister = useCallback(
    async ({ email, password, fullName }: RegisterValues) => {
      setJustRegistered(true);
      try {
        await register(email, password, fullName || undefined);
      } catch (err) {
        setJustRegistered(false);
        throw err;
      }
    },
    [register],
  );

  if (isLoading) return <LoadingScreen />;
  if (user) return <Navigate to={justRegistered ? FIRST_RUN_REDIRECT : DEFAULT_REDIRECT} replace />;

  return (
    <>
      <MeshBackground />
      <PageWrapper>
        <Center minH="80vh">
          <GlassCard hoverable={false} w="full" maxW="md" p={{ base: 6, md: 8 }}>
            <Stack spacing={6}>
              <Stack spacing={2}>
                <TextReveal text="Create your account" size="xl" />
                <Text color="text.muted">Find out what your repo is missing before your users do.</Text>
              </Stack>
              <RegisterForm onSubmit={handleRegister} />
              <HStack>
                <Divider />
                <Text fontSize="sm" color="text.muted" whiteSpace="nowrap">
                  or
                </Text>
                <Divider />
              </HStack>
              <GoogleLoginButton label="Sign up with Google" />
              <Text fontSize="sm" color="text.muted" textAlign="center">
                Already have an account?{' '}
                <Link as={RouterLink} to="/login" color="brand.600" fontWeight="semibold">
                  Sign in
                </Link>
              </Text>
            </Stack>
          </GlassCard>
        </Center>
      </PageWrapper>
    </>
  );
}
