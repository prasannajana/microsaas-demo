import { useNavigate } from 'react-router-dom';
import { Center, Text, VStack } from '@chakra-ui/react';
import { GlassCard } from '../components/ui/GlassCard';
import { GradientButton } from '../components/ui/GradientButton';
import { MeshBackground } from '../components/ui/MeshBackground';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <>
      <MeshBackground />
      <PageWrapper>
        <Center minH="70vh">
          <GlassCard hoverable={false} w="full" maxW="md" textAlign="center">
            <VStack spacing={4}>
              <TextReveal text="404 - Page not found" size="lg" />
              <Text color="text.muted">The page you are looking for does not exist.</Text>
              <GradientButton onClick={() => navigate('/')}>
                Go home
              </GradientButton>
            </VStack>
          </GlassCard>
        </Center>
      </PageWrapper>
    </>
  );
}
