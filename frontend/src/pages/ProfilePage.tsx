import { useState, type FormEvent } from 'react';
import { Avatar, Badge, chakra, HStack, SimpleGrid, Stack, Text, useToast } from '@chakra-ui/react';
import { useMutation } from '@tanstack/react-query';
import { AnimatedInput } from '../components/ui/AnimatedInput';
import { GlassCard } from '../components/ui/GlassCard';
import { GradientButton } from '../components/ui/GradientButton';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';
import { useAuth } from '../context/AuthContext';
import { getErrorMessage } from '../lib/errors';
import { updateMe } from '../services/authService';
import type { User } from '../types';

const MAX_NAME_LENGTH = 255;

function formatProvider(provider: string | null): string {
  if (!provider) return 'Email & password';
  return provider.charAt(0).toUpperCase() + provider.slice(1);
}

function formatMemberSince(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Stack spacing={1}>
      <Text fontSize="xs" textTransform="uppercase" letterSpacing="wider" color="text.muted" fontWeight="semibold">
        {label}
      </Text>
      <Text fontWeight="medium" wordBreak="break-word">
        {children}
      </Text>
    </Stack>
  );
}

function ProfileForm({ user }: { user: User }) {
  const { refreshUser } = useAuth();
  const toast = useToast();
  const [fullName, setFullName] = useState(user.full_name ?? '');
  const [error, setError] = useState<string | undefined>();

  const mutation = useMutation({
    mutationFn: (name: string) => updateMe({ full_name: name }),
    onSuccess: async () => {
      await refreshUser();
      toast({ title: 'Profile updated', status: 'success', duration: 3000, isClosable: true });
    },
    onError: (err: unknown) => {
      toast({
        title: 'Could not update profile',
        description: getErrorMessage(err),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    },
  });

  const trimmed = fullName.trim();
  const unchanged = trimmed === (user.full_name ?? '');

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!trimmed) {
      setError('Full name cannot be empty');
      return;
    }
    if (trimmed.length > MAX_NAME_LENGTH) {
      setError(`Full name must be at most ${MAX_NAME_LENGTH} characters`);
      return;
    }
    setError(undefined);
    mutation.mutate(trimmed);
  };

  return (
    <chakra.form onSubmit={handleSubmit} noValidate aria-label="Edit profile form">
      <Stack spacing={4}>
        <AnimatedInput
          name="fullName"
          label="Full name"
          autoComplete="name"
          placeholder="Your name"
          value={fullName}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFullName(e.target.value)}
          error={error}
        />
        <HStack justify="flex-end">
          <GradientButton type="submit" isLoading={mutation.isPending} isDisabled={unchanged} loadingText="Saving">
            Save changes
          </GradientButton>
        </HStack>
      </Stack>
    </chakra.form>
  );
}

export default function ProfilePage() {
  const { user } = useAuth();
  if (!user) return null;

  const displayName = user.full_name ?? user.email;

  return (
    <PageWrapper>
      <TextReveal text="Your profile" size="xl" mb={6} />
      <Stack spacing={6}>
        <GlassCard>
          <HStack spacing={5} align="center" flexWrap="wrap">
            <Avatar size="xl" name={displayName} src={user.avatar_url ?? undefined} />
            <Stack spacing={1} minW={0}>
              <Text fontSize="2xl" fontWeight="bold" noOfLines={1}>
                {displayName}
              </Text>
              <HStack spacing={2} flexWrap="wrap">
                {user.is_admin && <Badge colorScheme="purple">Admin</Badge>}
                {user.is_verified && <Badge colorScheme="green">Verified</Badge>}
              </HStack>
            </Stack>
          </HStack>
          <SimpleGrid columns={{ base: 1, md: 3 }} spacing={5} mt={6}>
            <DetailRow label="Email">{user.email}</DetailRow>
            <DetailRow label="Sign-in method">{formatProvider(user.oauth_provider)}</DetailRow>
            <DetailRow label="Member since">{formatMemberSince(user.created_at)}</DetailRow>
          </SimpleGrid>
        </GlassCard>
        <GlassCard hoverable={false}>
          <Text fontSize="lg" fontWeight="semibold" mb={4}>
            Edit details
          </Text>
          <ProfileForm user={user} />
        </GlassCard>
      </Stack>
    </PageWrapper>
  );
}
