import { Alert, AlertIcon, Breadcrumb, BreadcrumbItem, BreadcrumbLink, VStack } from '@chakra-ui/react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import { formatDateTime } from '../components/projects/format';
import { ScanReport } from '../components/projects/ScanReport';
import { ScanStatusBanner } from '../components/projects/ScanStatusBanner';
import { LoadingScreen } from '../components/ui/LoadingScreen';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';
import { useProject } from '../hooks/useProjects';
import { useScan } from '../hooks/useScans';
import { getErrorMessage } from '../lib/errors';

function parseId(raw: string | undefined): number | undefined {
  const n = Number(raw);
  return Number.isInteger(n) && n > 0 ? n : undefined;
}

export default function ScanReportPage() {
  const params = useParams<{ id: string; scanId: string }>();
  const projectId = parseId(params.id);
  const scanId = parseId(params.scanId);
  const scanQuery = useScan(scanId);
  const projectName = useProject(projectId).data?.name ?? 'Project';
  const scan = scanQuery.data;

  return (
    <PageWrapper>
      <Breadcrumb mb={4} fontSize="sm" color="text.muted">
        <BreadcrumbItem>
          <BreadcrumbLink as={RouterLink} to="/projects">
            Projects
          </BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbItem>
          <BreadcrumbLink as={RouterLink} to={projectId ? `/projects/${projectId}` : '/projects'}>
            {projectName}
          </BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbItem isCurrentPage>
          <BreadcrumbLink>Scan #{scanId ?? '?'}</BreadcrumbLink>
        </BreadcrumbItem>
      </Breadcrumb>

      <TextReveal
        text={scan ? `Scan from ${formatDateTime(scan.created_at)}` : 'Scan report'}
        size="lg"
        mb={6}
      />

      {scanId === undefined ? (
        <Alert status="error" borderRadius="xl">
          <AlertIcon />
          This scan link looks invalid.
        </Alert>
      ) : scanQuery.isLoading ? (
        <LoadingScreen fullScreen={false} />
      ) : scanQuery.isError || !scan ? (
        <Alert status="error" borderRadius="xl">
          <AlertIcon />
          {getErrorMessage(scanQuery.error, 'Could not load this scan.')}
        </Alert>
      ) : (
        <VStack align="stretch" spacing={6}>
          {scan.status !== 'completed' && <ScanStatusBanner scan={scan} />}
          {scan.status === 'completed' && <ScanReport scan={scan} />}
        </VStack>
      )}
    </PageWrapper>
  );
}
