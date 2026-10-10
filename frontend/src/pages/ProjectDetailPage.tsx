import {
  Alert,
  AlertIcon,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  Flex,
  Heading,
  HStack,
  Link,
  Tag,
  Text,
  useDisclosure,
  VStack,
} from '@chakra-ui/react';
import { Link as RouterLink, useLocation, useParams } from 'react-router-dom';
import { ActionButton } from '../components/projects/ActionButton';
import { DeleteProjectModal } from '../components/projects/DeleteProjectModal';
import { EditProjectModal } from '../components/projects/EditProjectModal';
import { formatRelativeTime } from '../components/projects/format';
import { RunScanButton } from '../components/projects/RunScanButton';
import { ScanHistoryTable } from '../components/projects/ScanHistoryTable';
import { ScanReport } from '../components/projects/ScanReport';
import { ScanStatusBanner } from '../components/projects/ScanStatusBanner';
import { useRunScan } from '../components/projects/useRunScan';
import { EmptyState } from '../components/ui/EmptyState';
import { GlassCard } from '../components/ui/GlassCard';
import { LoadingScreen } from '../components/ui/LoadingScreen';
import { PageWrapper } from '../components/ui/PageWrapper';
import { ScoreBadge } from '../components/ui/ScoreBadge';
import { useProject } from '../hooks/useProjects';
import { isActiveScanStatus, useProjectScans, useScan } from '../hooks/useScans';
import { getErrorMessage } from '../lib/errors';
import { repoSlugFromUrl } from '../lib/github';
import type { ScanDetail } from '../types';

interface LocationState {
  justCreated?: boolean;
}

function parseId(raw: string | undefined): number | undefined {
  const n = Number(raw);
  return Number.isInteger(n) && n > 0 ? n : undefined;
}

export default function ProjectDetailPage() {
  const projectId = parseId(useParams<{ id: string }>().id);
  const location = useLocation();
  const justCreated = (location.state as LocationState | null)?.justCreated === true;

  const projectQuery = useProject(projectId);
  const scansQuery = useProjectScans(projectId);
  const project = projectQuery.data;
  const scans = scansQuery.data ?? [];

  // Track the newest scan so we can poll it while it is queued/running.
  const newestId = scans[0]?.id ?? project?.latest_scan?.id;
  const trackedScan = useScan(newestId).data;
  const newestStatus = trackedScan?.status ?? scans[0]?.status ?? project?.latest_scan?.status;

  const { run, isPending } = useRunScan(projectId ?? 0);
  const scanActive = isPending || isActiveScanStatus(newestStatus);

  const editModal = useDisclosure();
  const deleteModal = useDisclosure();

  if (projectId === undefined) {
    return (
      <PageWrapper>
        <EmptyState title="Project not found" description="The link you followed looks invalid." />
      </PageWrapper>
    );
  }

  if (projectQuery.isLoading) {
    return (
      <PageWrapper>
        <LoadingScreen fullScreen={false} />
      </PageWrapper>
    );
  }

  if (projectQuery.isError || !project) {
    return (
      <PageWrapper>
        <Alert status="error" borderRadius="xl">
          <AlertIcon />
          {getErrorMessage(projectQuery.error, 'Could not load this project.')}
        </Alert>
      </PageWrapper>
    );
  }

  const latestCompleted: ScanDetail | null =
    trackedScan?.status === 'completed'
      ? trackedScan
      : project.latest_scan?.status === 'completed'
        ? project.latest_scan
        : null;
  const bannerScan = trackedScan ?? (scans[0] ? { status: scans[0].status, error_message: scans[0].error_message } : null);
  const slug = repoSlugFromUrl(project.repo_url) ?? project.repo_url;
  const hasScans = scans.length > 0 || project.latest_scan !== null;

  return (
    <PageWrapper>
      <Breadcrumb mb={4} fontSize="sm" color="text.muted">
        <BreadcrumbItem>
          <BreadcrumbLink as={RouterLink} to="/projects">
            Projects
          </BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbItem isCurrentPage>
          <BreadcrumbLink>{project.name}</BreadcrumbLink>
        </BreadcrumbItem>
      </Breadcrumb>

      <GlassCard hoverable={false} mb={6}>
        <Flex justify="space-between" align={{ base: 'stretch', md: 'center' }} direction={{ base: 'column', md: 'row' }} gap={4}>
          <VStack align="start" spacing={2} minW={0}>
            <HStack spacing={3} flexWrap="wrap">
              <Heading size="lg" wordBreak="break-word">
                {project.name}
              </Heading>
              <ScoreBadge score={project.latest_score} />
            </HStack>
            <Link
              href={project.repo_url}
              target="_blank"
              rel="noopener noreferrer"
              color="brand.600"
              fontWeight="medium"
              aria-label={`Open ${slug} on GitHub (opens in a new tab)`}
            >
              {slug} ↗
            </Link>
            <HStack spacing={2} flexWrap="wrap" fontSize="sm">
              {project.primary_language && (
                <Tag size="sm" borderRadius="full" colorScheme="brand">
                  {project.primary_language}
                </Tag>
              )}
              <Tag size="sm" borderRadius="full" variant="outline">
                Branch: {project.default_branch ?? 'default'}
              </Tag>
              <Text color="text.muted">
                {project.last_scanned_at ? `Last scanned ${formatRelativeTime(project.last_scanned_at)}` : 'Not scanned yet'}
              </Text>
            </HStack>
          </VStack>
          <HStack spacing={3} flexShrink={0} flexWrap="wrap">
            <ActionButton variant="outline" onClick={editModal.onOpen}>
              Edit
            </ActionButton>
            <ActionButton variant="outline" colorScheme="red" onClick={deleteModal.onOpen}>
              Delete
            </ActionButton>
            <RunScanButton onRun={run} isActive={scanActive} />
          </HStack>
        </Flex>
      </GlassCard>

      <VStack align="stretch" spacing={6}>
        {bannerScan && (
          <ScanStatusBanner scan={bannerScan} onRetry={run} isRetrying={isPending} />
        )}

        {!hasScans && !isPending ? (
          <EmptyState
            icon={<span>🔍</span>}
            title={justCreated ? 'Project added — run your first scan' : 'No scans yet'}
            description="Scan the repository to find missing essentials and get a 0-100 readiness score."
            action={<RunScanButton onRun={run} isActive={scanActive} label="Run first scan" size="lg" />}
          />
        ) : (
          latestCompleted && <ScanReport scan={latestCompleted} />
        )}

        {scans.length > 0 && (
          <GlassCard hoverable={false}>
            <Heading size="md" mb={4}>
              Scan history
            </Heading>
            <ScanHistoryTable projectId={project.id} scans={scans} />
          </GlassCard>
        )}
      </VStack>

      <EditProjectModal project={project} isOpen={editModal.isOpen} onClose={editModal.onClose} />
      <DeleteProjectModal project={project} isOpen={deleteModal.isOpen} onClose={deleteModal.onClose} />
    </PageWrapper>
  );
}
