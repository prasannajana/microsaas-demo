import { Tag, type TagProps } from '@chakra-ui/react';
import type { Severity } from '../../types';
import { SEVERITY_COLOR_SCHEME, SEVERITY_LABEL } from '../../lib/score';

export interface SeverityTagProps extends Omit<TagProps, 'children' | 'colorScheme'> {
  severity: Severity;
}

/** critical red, high orange, medium yellow, low gray. */
export function SeverityTag({ severity, ...rest }: SeverityTagProps) {
  return (
    <Tag
      colorScheme={SEVERITY_COLOR_SCHEME[severity]}
      variant="subtle"
      borderRadius="full"
      fontWeight="semibold"
      textTransform="uppercase"
      fontSize="xs"
      letterSpacing="wide"
      {...rest}
    >
      {SEVERITY_LABEL[severity]}
    </Tag>
  );
}
