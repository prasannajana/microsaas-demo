import { useEffect, useState, type ChangeEvent } from 'react';
import {
  Alert,
  AlertDescription,
  AlertIcon,
  Avatar,
  Badge,
  HStack,
  Skeleton,
  Switch,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  useToast,
} from '@chakra-ui/react';
import { AdminTableCard } from '../components/admin/AdminTableCard';
import { formatDate } from '../components/admin/format';
import { Pagination } from '../components/admin/Pagination';
import { AnimatedInput } from '../components/ui/AnimatedInput';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';
import { useAuth } from '../context/AuthContext';
import { useAdminUsers, useUpdateAdminUser } from '../hooks/useAdmin';
import { getErrorMessage } from '../lib/errors';
import type { AdminUserUpdate, User } from '../types';

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 300;

function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

export default function AdminUsersPage() {
  const { user: me } = useAuth();
  const toast = useToast();
  const [search, setSearch] = useState('');
  const q = useDebouncedValue(search.trim(), SEARCH_DEBOUNCE_MS);
  // Page is remembered per search term so a new search starts at page 1.
  const [pageState, setPageState] = useState<{ q: string; page: number }>({ q: '', page: 1 });
  const page = pageState.q === q ? pageState.page : 1;
  const setPage = (next: number) => setPageState({ q, page: next });

  const { data, isLoading, isError, error, isFetching } = useAdminUsers({ page, size: PAGE_SIZE, q: q || undefined });
  const updateUser = useUpdateAdminUser();
  const pendingId = updateUser.isPending ? updateUser.variables?.id : undefined;

  function handleToggle(target: User, update: AdminUserUpdate) {
    updateUser.mutate(
      { id: target.id, update },
      {
        onSuccess: (updated) => {
          toast({ status: 'success', title: `Updated ${updated.email}`, duration: 2500, isClosable: true });
        },
        onError: (err) => {
          toast({ status: 'error', title: 'Update failed', description: getErrorMessage(err), isClosable: true });
        },
      },
    );
  }

  return (
    <PageWrapper>
      <TextReveal text="Users" size="xl" mb={6} />

      <AnimatedInput
        name="user-search"
        aria-label="Search users"
        placeholder="Search by email or name"
        value={search}
        onChange={(e: ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
        mb={6}
        maxW="md"
      />

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
              <Th>Email</Th>
              <Th>Name</Th>
              <Th>Provider</Th>
              <Th>Created</Th>
              <Th>Active</Th>
              <Th>Admin</Th>
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
                    No users match your search.
                  </Text>
                </Td>
              </Tr>
            )}
            {data?.items.map((u) => {
              const isSelf = me?.id === u.id;
              const disabled = isSelf || pendingId === u.id;
              return (
                <Tr key={u.id} data-testid={`user-row-${u.id}`} _hover={{ bg: 'blackAlpha.50' }}>
                  <Td>
                    <HStack spacing={2}>
                      <Avatar size="xs" name={u.full_name ?? u.email} src={u.avatar_url ?? undefined} />
                      <Text>{u.email}</Text>
                      {isSelf && (
                        <Badge colorScheme="brand" variant="subtle">
                          You
                        </Badge>
                      )}
                    </HStack>
                  </Td>
                  <Td>{u.full_name ?? '—'}</Td>
                  <Td textTransform="capitalize">{u.oauth_provider ?? 'email'}</Td>
                  <Td whiteSpace="nowrap">{formatDate(u.created_at)}</Td>
                  <Td>
                    <Switch
                      colorScheme="green"
                      isChecked={u.is_active}
                      isDisabled={disabled}
                      aria-label={`Active status for ${u.email}`}
                      onChange={(e) => handleToggle(u, { is_active: e.target.checked })}
                    />
                  </Td>
                  <Td>
                    <Switch
                      colorScheme="brand"
                      isChecked={u.is_admin}
                      isDisabled={disabled}
                      aria-label={`Admin access for ${u.email}`}
                      onChange={(e) => handleToggle(u, { is_admin: e.target.checked })}
                    />
                  </Td>
                </Tr>
              );
            })}
          </Tbody>
        </Table>
      </AdminTableCard>

      {data && (
        <Pagination page={page} size={PAGE_SIZE} total={data.total} onPageChange={setPage} isDisabled={isFetching} />
      )}
    </PageWrapper>
  );
}
