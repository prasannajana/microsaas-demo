import { HStack, Text } from '@chakra-ui/react';
import { MotionButton } from '../ui/motion';

export interface PaginationProps {
  page: number;
  size: number;
  total: number;
  onPageChange: (page: number) => void;
  isDisabled?: boolean;
}

/** Previous / next pager with "Page X of Y". */
export function Pagination({ page, size, total, onPageChange, isDisabled = false }: PaginationProps) {
  const pageCount = Math.max(1, Math.ceil(total / size));
  const canPrev = page > 1 && !isDisabled;
  const canNext = page < pageCount && !isDisabled;
  return (
    <HStack justify="space-between" mt={4} wrap="wrap" gap={2}>
      <Text fontSize="sm" color="text.muted">
        {total} result{total === 1 ? '' : 's'} · Page {page} of {pageCount}
      </Text>
      <HStack spacing={2}>
        <MotionButton
          size="sm"
          variant="outline"
          whileHover={canPrev ? { y: -2 } : undefined}
          whileTap={canPrev ? { scale: 0.95 } : undefined}
          isDisabled={!canPrev}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </MotionButton>
        <MotionButton
          size="sm"
          variant="outline"
          whileHover={canNext ? { y: -2 } : undefined}
          whileTap={canNext ? { scale: 0.95 } : undefined}
          isDisabled={!canNext}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </MotionButton>
      </HStack>
    </HStack>
  );
}
