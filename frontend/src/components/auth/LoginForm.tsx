import { useState, type FormEvent } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { isAxiosError } from 'axios';
import { Alert, AlertDescription, AlertIcon, Box, chakra, Link, Stack } from '@chakra-ui/react';
import { AnimatedInput } from '../ui/AnimatedInput';
import { GradientButton } from '../ui/GradientButton';
import { getErrorMessage } from '../../lib/errors';
import { isValidEmail } from '../../services/authService';

export interface LoginFormProps {
  /** Performs the login; rejects on failure (error is shown inline above the button). */
  onSubmit: (email: string, password: string) => Promise<void>;
}

interface LoginErrors {
  email?: string;
  password?: string;
}

function validate(email: string, password: string): LoginErrors {
  const errors: LoginErrors = {};
  if (!email.trim()) errors.email = 'Email is required';
  else if (!isValidEmail(email)) errors.email = 'Enter a valid email address';
  if (!password) errors.password = 'Password is required';
  return errors;
}

/** True when the server rejected the credentials (unknown email or wrong password). */
function isBadCredentials(err: unknown): boolean {
  return isAxiosError(err) && err.response?.status === 401;
}

export function LoginForm({ onSubmit }: LoginFormProps) {
  const [formError, setFormError] = useState<{ message: string; suggestRegister: boolean } | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<LoginErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors = validate(email, password);
    setErrors(nextErrors);
    setFormError(null);
    if (Object.keys(nextErrors).length > 0) return;

    setIsSubmitting(true);
    try {
      await onSubmit(email.trim(), password);
    } catch (err) {
      const badCredentials = isBadCredentials(err);
      setFormError({
        message: badCredentials ? 'Incorrect email or password.' : getErrorMessage(err),
        suggestRegister: badCredentials,
      });
      setIsSubmitting(false);
    }
  };

  return (
    <chakra.form onSubmit={handleSubmit} noValidate aria-label="Sign in form">
      <Stack spacing={4}>
        <AnimatedInput
          name="email"
          type="email"
          label="Email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
          error={errors.email}
        />
        <AnimatedInput
          name="password"
          type="password"
          label="Password"
          autoComplete="current-password"
          placeholder="Your password"
          value={password}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
          error={errors.password}
        />
        {formError && (
          <Alert status="error" borderRadius="xl" role="alert">
            <AlertIcon />
            <Box>
              <AlertDescription display="block">{formError.message}</AlertDescription>
              {formError.suggestRegister && (
                <AlertDescription display="block" fontSize="sm" mt={1}>
                  Don&apos;t have an account yet?{' '}
                  <Link as={RouterLink} to="/register" state={{ email: email.trim() }} fontWeight="semibold" textDecoration="underline">
                    Create one with this email
                  </Link>
                </AlertDescription>
              )}
            </Box>
          </Alert>
        )}
        <GradientButton type="submit" size="lg" w="full" isLoading={isSubmitting} loadingText="Signing in">
          Sign in
        </GradientButton>
      </Stack>
    </chakra.form>
  );
}
