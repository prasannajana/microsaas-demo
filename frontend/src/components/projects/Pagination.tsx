import { HStack, Text } from '@chakra-ui/react';
import { ActionButton } from './ActionButton';

export interface PaginationProps {
  page: number;
  size: number;
  total: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, size, total, onChange }: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / size));
  if (pages <= 1) return null;
  return (
    <HStack as="nav" aria-label="Pagination" justify="center" spacing={4}>
      <ActionButton size="sm" variant="outline" onClick={() => onChange(page - 1)} isDisabled={page <= 1}>
        Previous
      </ActionButton>
      <Text fontSize="sm" color="text.muted" aria-live="polite">
        Page {page} of {pages}
      </Text>
      <ActionButton size="sm" variant="outline" onClick={() => onChange(page + 1)} isDisabled={page >= pages}>
        Next
      </ActionButton>
    </HStack>
  );
}
