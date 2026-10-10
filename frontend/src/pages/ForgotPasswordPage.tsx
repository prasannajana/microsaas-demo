import { useState, type FormEvent } from 'react';
import { Alert, AlertDescription, AlertIcon, Center, chakra, Link, Stack, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';
import { AnimatedInput } from '../components/ui/AnimatedInput';
import { GlassCard } from '../components/ui/GlassCard';
import { GradientButton } from '../components/ui/GradientButton';
import { MeshBackground } from '../components/ui/MeshBackground';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';
import { isValidEmail } from '../services/authService';

/**
 * Password reset by email is post-MVP. This page is intentionally UI-only:
 * it makes no API call and tells the user plainly to contact support.
 */
export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | undefined>();
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isValidEmail(email)) {
      setError('Enter a valid email address');
      return;
    }
    setError(undefined);
    setSubmitted(true);
  };

  return (
    <>
      <MeshBackground />
      <PageWrapper>
        <Center minH="80vh">
          <GlassCard hoverable={false} w="full" maxW="md" p={{ base: 6, md: 8 }}>
            <Stack spacing={6}>
              <Stack spacing={2}>
                <TextReveal text="Forgot your password?" size="xl" />
                <Text color="text.muted">
                  Password reset by email is coming soon — contact support and we&apos;ll help you regain access.
                </Text>
              </Stack>
              {submitted ? (
                <Alert status="info" borderRadius="xl">
                  <AlertIcon />
                  <AlertDescription>
                    We haven&apos;t sent an email — automated resets aren&apos;t available yet. Please contact
                    support from {email.trim()} and we&apos;ll reset your password manually.
                  </AlertDescription>
                </Alert>
              ) : (
                <chakra.form onSubmit={handleSubmit} noValidate>
                  <Stack spacing={4}>
                    <AnimatedInput
                      name="email"
                      type="email"
                      label="Email"
                      autoComplete="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
                      error={error}
                    />
                    <GradientButton type="submit" size="lg" w="full">
                      Continue
                    </GradientButton>
                  </Stack>
                </chakra.form>
              )}
              <Text fontSize="sm" textAlign="center">
                <Link as={RouterLink} to="/login" color="brand.600" fontWeight="semibold">
                  Back to sign in
                </Link>
              </Text>
            </Stack>
          </GlassCard>
        </Center>
      </PageWrapper>
    </>
  );
}
