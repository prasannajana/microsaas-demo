import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, AlertDescription, AlertIcon, Box, SimpleGrid, Text } from '@chakra-ui/react';
import { CommonFindingsList } from '../components/dashboard/CommonFindingsList';
import { ProjectsQuickList } from '../components/dashboard/ProjectsQuickList';
import type { TrendRange } from '../components/dashboard/chartPalette';
import { ScoreTrendChart } from '../components/dashboard/ScoreTrendChart';
import { StatCard } from '../components/dashboard/StatCard';
import { EmptyState } from '../components/ui/EmptyState';
import { GradientButton } from '../components/ui/GradientButton';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';
import { useAuth } from '../context/AuthContext';
import { useAnalyticsSummary, useCommonFindings, useDashboardProjects, useScoreTrend } from '../hooks/useAnalytics';
import { getErrorMessage } from '../lib/errors';
import { getScoreColorScheme } from '../lib/score';

function firstName(fullName: string | null | undefined, email: string | undefined): string {
  const name = fullName?.trim();
  if (name) return name.split(/\s+/)[0] ?? name;
  if (email) return email.split('@')[0] ?? email;
  return 'there';
}

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [days, setDays] = useState<TrendRange>(30);
  const summary = useAnalyticsSummary();
  const isFirstRun = summary.data?.project_count === 0;
  const trend = useScoreTrend(days);
  const findings = useCommonFindings(5);
  const projects = useDashboardProjects(5);

  const greeting = `Welcome back, ${firstName(user?.full_name, user?.email)}`;
  const avg = summary.data?.avg_latest_score ?? null;

  return (
    <PageWrapper>
      <TextReveal text={greeting} size="xl" mb={2} />
      <Text color="text.muted" mb={8}>
        Here is how your projects are doing.
      </Text>

      {summary.isError && (
        <Alert status="error" borderRadius="lg" mb={6}>
          <AlertIcon />
          <AlertDescription>{getErrorMessage(summary.error)}</AlertDescription>
        </Alert>
      )}

      {isFirstRun ? (
        <EmptyState
          icon="🚀"
          title="Add your first project"
          description="Connect a GitHub repository to get a readiness score and a list of what's missing."
          action={
            <GradientButton onClick={() => navigate('/projects/new')}>
              Add a project
            </GradientButton>
          }
        />
      ) : (
        <>
          <SimpleGrid columns={{ base: 1, sm: 2, lg: 4 }} spacing={4} mb={6}>
            <StatCard label="Projects" value={summary.data?.project_count ?? 0} isLoading={summary.isLoading} />
            <StatCard label="Scans run" value={summary.data?.scan_count ?? 0} isLoading={summary.isLoading} />
            <StatCard
              label="Average score"
              value={avg === null ? '—' : `${Math.round(avg)}`}
              helpText={avg === null ? 'No completed scans yet' : 'out of 100'}
              valueColor={avg === null ? undefined : `${getScoreColorScheme(avg)}.500`}
              isLoading={summary.isLoading}
            />
            <StatCard
              label="Open critical findings"
              value={summary.data?.open_critical_findings ?? 0}
              valueColor={summary.data && summary.data.open_critical_findings > 0 ? 'red.500' : undefined}
              isLoading={summary.isLoading}
            />
          </SimpleGrid>

          <Box mb={6}>
            <ScoreTrendChart series={trend.data} days={days} onDaysChange={setDays} isLoading={trend.isLoading} />
          </Box>

          <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
            <CommonFindingsList findings={findings.data} isLoading={findings.isLoading} />
            <ProjectsQuickList
              projects={projects.data?.items}
              total={projects.data?.total}
              isLoading={projects.isLoading}
            />
          </SimpleGrid>
        </>
      )}
    </PageWrapper>
  );
}
