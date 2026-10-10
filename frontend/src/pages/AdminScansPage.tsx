import { useState, type ChangeEvent } from 'react';
import {
  Alert,
  AlertDescription,
  AlertIcon,
  FormControl,
  FormLabel,
  Select,
  Skeleton,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tooltip,
  Tr,
} from '@chakra-ui/react';
import { AdminTableCard } from '../components/admin/AdminTableCard';
import { formatDateTime } from '../components/admin/format';
import { Pagination } from '../components/admin/Pagination';
import { ScanStatusBadge } from '../components/admin/ScanStatusBadge';
import { PageWrapper } from '../components/ui/PageWrapper';
import { ScoreBadge } from '../components/ui/ScoreBadge';
import { TextReveal } from '../components/ui/TextReveal';
import { useAdminScans } from '../hooks/useAdmin';
import { getErrorMessage } from '../lib/errors';
import { SCAN_STATUSES, type ScanStatus } from '../types';

const PAGE_SIZE = 20;

function isScanStatus(value: string): value is ScanStatus {
  return (SCAN_STATUSES as readonly string[]).includes(value);
}

export default function AdminScansPage() {
  const [status, setStatus] = useState<ScanStatus | undefined>(undefined);
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, error, isFetching } = useAdminScans({ status, page, size: PAGE_SIZE });

  function handleStatusChange(e: ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value;
    setStatus(isScanStatus(value) ? value : undefined);
    setPage(1);
  }

  return (
    <PageWrapper>
      <TextReveal text="Scans" size="xl" mb={6} />

      <FormControl maxW="xs" mb={6}>
        <FormLabel htmlFor="status-filter">Status</FormLabel>
        <Select id="status-filter" value={status ?? 'all'} onChange={handleStatusChange} borderRadius="xl">
          <option value="all">All statuses</option>
          {SCAN_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </Select>
      </FormControl>

      {isError && (
        <Alert status="error" borderRadius="lg" mb={6}>
          <AlertIcon />
          <AlertDescription>{getErrorMessage(error)}</AlertDescription>
        </Alert>
      )}

      <AdminTableCard>
        <Table size="sm" variant="simple">
          <Thead>
            <Tr>
              <Th>Created</Th>
              <Th>Project</Th>
              <Th>User</Th>
              <Th>Status</Th>
              <Th>Score</Th>
              <Th>Error</Th>
            </Tr>
          </Thead>
          <Tbody>
            {isLoading &&
              [0, 1, 2, 3].map((i) => (
                <Tr key={`sk-${i}`}>
                  <Td colSpan={6}>
                    <Skeleton h="1.5rem" />
                  </Td>
                </Tr>
              ))}
            {data?.items.length === 0 && (
              <Tr>
                <Td colSpan={6}>
                  <Text color="text.muted" py={4} textAlign="center">
                    No scans found.
                  </Text>
                </Td>
              </Tr>
            )}
            {data?.items.map((s) => (
              <Tr key={s.id} _hover={{ bg: 'blackAlpha.50' }}>
                <Td whiteSpace="nowrap">{formatDateTime(s.created_at)}</Td>
                <Td>{s.project_name}</Td>
                <Td>{s.user_email}</Td>
                <Td>
                  <ScanStatusBadge status={s.status} />
                </Td>
                <Td>{s.status === 'completed' ? <ScoreBadge score={s.score} fontSize="xs" /> : '—'}</Td>
                <Td>
                  {s.error_message ? (
                    <Tooltip label={s.error_message} hasArrow placement="top-start" maxW="sm">
                      <Text as="span" color="red.500" cursor="help" noOfLines={1} maxW="12rem" tabIndex={0}>
                        {s.error_message}
                      </Text>
                    </Tooltip>
                  ) : (
                    '—'
                  )}
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </AdminTableCard>

      {data && (
        <Pagination page={page} size={PAGE_SIZE} total={data.total} onPageChange={setPage} isDisabled={isFetching} />
      )}
    </PageWrapper>
  );
}
