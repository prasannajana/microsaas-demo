import {
  Accordion,
  AccordionButton,
  AccordionIcon,
  AccordionItem,
  AccordionPanel,
  Badge,
  Box,
  HStack,
  Text,
} from '@chakra-ui/react';
import type { FindingOut } from '../../types';
import { AnimatedList } from '../ui/AnimatedList';
import { SeverityTag } from '../ui/SeverityTag';
import { FindingCard } from './FindingCard';
import { groupFindingsByCategory } from './format';

export interface FindingsByCategoryProps {
  findings: readonly FindingOut[];
}

/** Accordion of findings grouped by category; every group starts expanded. */
export function FindingsByCategory({ findings }: FindingsByCategoryProps) {
  const groups = groupFindingsByCategory(findings);
  return (
    <Accordion allowMultiple defaultIndex={groups.map((_, i) => i)} data-testid="findings-by-category">
      {groups.map((group) => {
        const top = group.findings[0];
        return (
          <AccordionItem key={group.category} border="none" mb={3} data-testid={`category-${group.category}`}>
            <h3>
              <AccordionButton borderRadius="xl" bg="whiteAlpha.600" _hover={{ bg: 'brand.50' }} px={4} py={3}>
                <HStack flex="1" spacing={3} textAlign="left">
                  <Text fontWeight="semibold">{group.label}</Text>
                  <Badge borderRadius="full" colorScheme="brand" aria-label={`${group.findings.length} findings`}>
                    {group.findings.length}
                  </Badge>
                  {top && <SeverityTag severity={top.severity} size="sm" />}
                </HStack>
                <AccordionIcon />
              </AccordionButton>
            </h3>
            <AccordionPanel px={0} pt={3} pb={1}>
              <Box>
                <AnimatedList
                  items={group.findings}
                  getKey={(f) => f.id}
                  gap={3}
                  renderItem={(f) => <FindingCard finding={f} />}
                />
              </Box>
            </AccordionPanel>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}
