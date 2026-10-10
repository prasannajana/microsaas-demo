import { useState, type FormEvent } from 'react';
import { useLocation } from 'react-router-dom';
import { chakra, Stack, useToast } from '@chakra-ui/react';
import { AnimatedInput } from '../ui/AnimatedInput';
import { GradientButton } from '../ui/GradientButton';
import { getErrorMessage } from '../../lib/errors';
import { isValidEmail, MIN_PASSWORD_LENGTH } from '../../services/authService';

export interface RegisterValues {
  fullName: string;
  email: string;
  password: string;
}

export interface RegisterFormProps {
  /** Performs the registration; rejects on failure (error is shown as a toast). */
  onSubmit: (values: RegisterValues) => Promise<void>;
}

interface RegisterErrors {
  email?: string;
  password?: string;
  confirmPassword?: string;
}

function validate(email: string, password: string, confirmPassword: string): RegisterErrors {
  const errors: RegisterErrors = {};
  if (!email.trim()) errors.email = 'Email is required';
  else if (!isValidEmail(email)) errors.email = 'Enter a valid email address';
  if (password.length < MIN_PASSWORD_LENGTH) {
    errors.password = `Password must be at least ${MIN_PASSWORD_LENGTH} characters`;
  }
  if (!confirmPassword) errors.confirmPassword = 'Please confirm your password';
  else if (confirmPassword !== password) errors.confirmPassword = 'Passwords do not match';
  return errors;
}

export function RegisterForm({ onSubmit }: RegisterFormProps) {
  const toast = useToast();
  const [fullName, setFullName] = useState('');
  const location = useLocation();
  const prefillEmail = (location.state as { email?: unknown } | null)?.email;
  const [email, setEmail] = useState(typeof prefillEmail === 'string' ? prefillEmail : '');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<RegisterErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors = validate(email, password, confirmPassword);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setIsSubmitting(true);
    try {
      await onSubmit({ fullName: fullName.trim(), email: email.trim(), password });
    } catch (err) {
      toast({
        title: 'Registration failed',
        description: getErrorMessage(err),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsSubmitting(false);
    }
  };

  return (
    <chakra.form onSubmit={handleSubmit} noValidate aria-label="Create account form">
      <Stack spacing={4}>
        <AnimatedInput
          name="fullName"
          label="Full name (optional)"
          autoComplete="name"
          placeholder="Ada Lovelace"
          value={fullName}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFullName(e.target.value)}
        />
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
          autoComplete="new-password"
          placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
          value={password}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
          error={errors.password}
        />
        <AnimatedInput
          name="confirmPassword"
          type="password"
          label="Confirm password"
          autoComplete="new-password"
          placeholder="Repeat your password"
          value={confirmPassword}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setConfirmPassword(e.target.value)}
          error={errors.confirmPassword}
        />
        <GradientButton type="submit" size="lg" w="full" isLoading={isSubmitting} loadingText="Creating account">
          Create account
        </GradientButton>
      </Stack>
    </chakra.form>
  );
}
