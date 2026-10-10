import { useState } from 'react';
import { Stack, Text } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';
import { GlassCard } from '../components/ui/GlassCard';
import { MotionButton } from '../components/ui/motion';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';
import { useAuth } from '../context/AuthContext';

const buttonMotion = { whileHover: { scale: 1.03, y: -2 }, whileTap: { scale: 0.97 } } as const;

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isSigningOut, setIsSigningOut] = useState(false);

  const handleSignOut = async () => {
    setIsSigningOut(true);
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <PageWrapper>
      <TextReveal text="Settings" size="xl" mb={6} />
      <Stack spacing={6} maxW="2xl">
        <GlassCard>
          <Stack spacing={3} align="flex-start">
            <Text fontSize="lg" fontWeight="semibold">
              Account
            </Text>
            <Text color="text.muted">
              Signed in as <Text as="span" fontWeight="semibold" color="gray.800">{user?.email}</Text>. Update your
              name and view account details on your profile.
            </Text>
            <MotionButton variant="outline" onClick={() => navigate('/profile')} {...buttonMotion}>
              Go to profile
            </MotionButton>
          </Stack>
        </GlassCard>
        <GlassCard>
          <Stack spacing={3} align="flex-start">
            <Text fontSize="lg" fontWeight="semibold">
              Session
            </Text>
            <Text color="text.muted">Sign out of Project Verification on this device.</Text>
            <MotionButton
              colorScheme="red"
              variant="outline"
              onClick={handleSignOut}
              isLoading={isSigningOut}
              loadingText="Signing out"
              {...buttonMotion}
            >
              Sign out
            </MotionButton>
          </Stack>
        </GlassCard>
      </Stack>
    </PageWrapper>
  );
}
