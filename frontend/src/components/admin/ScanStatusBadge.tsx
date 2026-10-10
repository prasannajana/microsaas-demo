import { Badge, type BadgeProps } from '@chakra-ui/react';
import type { ScanStatus } from '../../types';

const STATUS_COLOR: Record<ScanStatus, string> = {
  queued: 'gray',
  running: 'blue',
  completed: 'green',
  failed: 'red',
};

export interface ScanStatusBadgeProps extends Omit<BadgeProps, 'children' | 'colorScheme'> {
  status: ScanStatus;
}

export function ScanStatusBadge({ status, ...rest }: ScanStatusBadgeProps) {
  return (
    <Badge colorScheme={STATUS_COLOR[status]} borderRadius="full" px={2} textTransform="capitalize" {...rest}>
      {status}
    </Badge>
  );
}
