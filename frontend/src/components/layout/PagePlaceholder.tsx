import { Text } from '@chakra-ui/react';
import { GlassCard } from '../ui/GlassCard';
import { PageWrapper } from '../ui/PageWrapper';
import { TextReveal } from '../ui/TextReveal';

export interface PagePlaceholderProps {
  title: string;
  description?: string;
}

/** Temporary page body used until the feature agent implements the real page. */
export function PagePlaceholder({ title, description = 'This page is coming soon.' }: PagePlaceholderProps) {
  return (
    <PageWrapper>
      <TextReveal text={title} size="xl" mb={6} />
      <GlassCard hoverable={false}>
        <Text color="text.muted">{description}</Text>
      </GlassCard>
    </PageWrapper>
  );
}
