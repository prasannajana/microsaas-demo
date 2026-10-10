import { Badge, Box, Link, Table, Tbody, Td, Text, Th, Thead, Tr } from '@chakra-ui/react';
import { motion, type Variants } from 'framer-motion';
import { Link as RouterLink } from 'react-router-dom';
import type { ScanStatus, ScanSummary } from '../../types';
import { ScoreBadge } from '../ui/ScoreBadge';
import { formatDateTime } from './format';
import { withScoreDeltas } from './scanHistory';

const MotionTbody = motion.create(Tbody);
const MotionTr = motion.create(Tr);

const bodyVariants: Variants = { hidden: {}, visible: { transition: { staggerChildren: 0.05 } } };
const rowVariants: Variants = { hidden: { opacity: 0, y: 8 }, visible: { opacity: 1, y: 0 } };

const STATUS_SCHEME: Record<ScanStatus, string> = {
  queued: 'gray',
  running: 'blue',
  completed: 'green',
  failed: 'red',
};

export interface ScanHistoryTableProps {
  projectId: number;
  scans: readonly ScanSummary[];
}

function DeltaText({ delta }: { delta: number | null }) {
  if (delta === null) return <Text color="text.muted">—</Text>;
  if (delta === 0) return <Text color="text.muted">±0</Text>;
  const up = delta > 0;
  return (
    <Text
      fontWeight="semibold"
      color={up ? 'green.600' : 'red.600'}
      aria-label={`${up ? 'Up' : 'Down'} ${Math.abs(delta)} points from previous scan`}
    >
      {up ? `▲ +${delta}` : `▼ ${delta}`}
    </Text>
  );
}

export function ScanHistoryTable({ projectId, scans }: ScanHistoryTableProps) {
  const rows = withScoreDeltas(scans);
  return (
    <Box overflowX="auto">
      <Table size="sm" variant="simple" aria-label="Scan history">
        <Thead>
          <Tr>
            <Th>Date</Th>
            <Th>Status</Th>
            <Th>Score</Th>
            <Th>Change</Th>
            <Th>
              <Text as="span" srOnly>
                Report
              </Text>
            </Th>
          </Tr>
        </Thead>
        <MotionTbody initial="hidden" animate="visible" variants={bodyVariants}>
          {rows.map(({ scan, delta }) => (
            <MotionTr key={scan.id} variants={rowVariants} _hover={{ bg: 'brand.50' }}>
              <Td whiteSpace="nowrap">{formatDateTime(scan.created_at)}</Td>
              <Td>
                <Badge colorScheme={STATUS_SCHEME[scan.status]} borderRadius="full" textTransform="capitalize">
                  {scan.status}
                </Badge>
              </Td>
              <Td>{scan.status === 'completed' ? <ScoreBadge score={scan.score} /> : <Text color="text.muted">—</Text>}</Td>
              <Td>
                <DeltaText delta={delta} />
              </Td>
              <Td textAlign="right">
                <Link
                  as={RouterLink}
                  to={`/projects/${projectId}/scans/${scan.id}`}
                  color="brand.600"
                  fontWeight="medium"
                  aria-label={`View scan from ${formatDateTime(scan.created_at)}`}
                >
                  View
                </Link>
              </Td>
            </MotionTr>
          ))}
        </MotionTbody>
      </Table>
    </Box>
  );
}
