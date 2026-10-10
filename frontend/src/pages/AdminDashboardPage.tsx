import { useNavigate } from 'react-router-dom';
import { Alert, AlertDescription, AlertIcon, Heading, SimpleGrid, Stack, Text } from '@chakra-ui/react';
import { formatFailureRate } from '../components/admin/format';
import { StatCard } from '../components/dashboard/StatCard';
import { AnimatedList } from '../components/ui/AnimatedList';
import { GlassCard } from '../components/ui/GlassCard';
import { GradientButton } from '../components/ui/GradientButton';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';
import { useAdminStats } from '../hooks/useAdmin';
import { getErrorMessage } from '../lib/errors';

interface AdminLink {
  to: string;
  title: string;
  description: string;
  cta: string;
}

const LINKS: AdminLink[] = [
  { to: '/admin/users', title: 'Users', description: 'Search accounts, deactivate users and manage admin access.', cta: 'Manage users' },
  { to: '/admin/scans', title: 'Scans', description: 'Review recent scans across all users and investigate failures.', cta: 'View scans' },
];

export default function AdminDashboardPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError, error } = useAdminStats();
  const failureColor = data && data.failure_rate >= 0.2 ? 'red.500' : undefined;

  return (
    <PageWrapper>
      <TextReveal text="Admin" size="xl" mb={2} />
      <Text color="text.muted" mb={8}>
        Platform-wide statistics.
      </Text>

      {isError && (
        <Alert status="error" borderRadius="lg" mb={6}>
          <AlertIcon />
          <AlertDescription>{getErrorMessage(error)}</AlertDescription>
        </Alert>
      )}

      <SimpleGrid columns={{ base: 1, sm: 2, lg: 5 }} spacing={4} mb={8}>
        <StatCard label="Users" value={data?.user_count ?? 0} isLoading={isLoading} />
        <StatCard label="Projects" value={data?.project_count ?? 0} isLoading={isLoading} />
        <StatCard label="Scans" value={data?.scan_count ?? 0} isLoading={isLoading} />
        <StatCard label="Scans (24h)" value={data?.scans_last_24h ?? 0} isLoading={isLoading} />
        <StatCard
          label="Failure rate"
          value={data ? formatFailureRate(data.failure_rate) : '—'}
          valueColor={failureColor}
          isLoading={isLoading}
        />
      </SimpleGrid>

      <AnimatedList
        items={LINKS}
        getKey={(l) => l.to}
        display="grid"
        gridTemplateColumns={{ base: '1fr', md: '1fr 1fr' }}
        gap={6}
        renderItem={(l) => (
          <GlassCard h="full">
            <Stack spacing={3} align="flex-start">
              <Heading size="md">{l.title}</Heading>
              <Text color="text.muted">{l.description}</Text>
              <GradientButton size="sm" onClick={() => navigate(l.to)}>
                {l.cta}
              </GradientButton>
            </Stack>
          </GlassCard>
        )}
      />
    </PageWrapper>
  );
}
