import type { ReactNode } from 'react';
import { Box, Heading, Text, VStack } from '@chakra-ui/react';
import { GlassCard } from './GlassCard';

export interface EmptyStateProps {
  title: string;
  description?: string;
  /** Optional visual (emoji, icon element, illustration). */
  icon?: ReactNode;
  /** Optional call to action, e.g. a GradientButton. */
  action?: ReactNode;
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <GlassCard hoverable={false} py={12} textAlign="center">
      <VStack spacing={4}>
        {icon && (
          <Box fontSize="4xl" color="brand.500" aria-hidden="true">
            {icon}
          </Box>
        )}
        <Heading size="md">{title}</Heading>
        {description && (
          <Text color="text.muted" maxW="md">
            {description}
          </Text>
        )}
        {action}
      </VStack>
    </GlassCard>
  );
}
