import { useMemo } from 'react';
import { Box, ButtonGroup, Flex, Heading, HStack, Skeleton, Text, useColorModeValue, useToken } from '@chakra-ui/react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
  type TooltipValueType,
} from 'recharts';
import type { ScoreTrendSeries } from '../../types';
import { GlassCard } from '../ui/GlassCard';
import { MotionButton } from '../ui/motion';
import { MAX_SERIES, SERIES_PALETTE_DARK, SERIES_PALETTE_LIGHT, TREND_RANGES, type TrendRange } from './chartPalette';

type ChartRow = { date: string } & Record<string, number | string>;

interface SeriesMeta {
  key: string;
  name: string;
  color: string;
}

export interface ScoreTrendChartProps {
  series: ScoreTrendSeries[] | undefined;
  days: TrendRange;
  onDaysChange: (days: TrendRange) => void;
  isLoading?: boolean;
}

function formatDay(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Pivot per-project series into one row per date; last score of a day wins. */
function buildRows(series: ScoreTrendSeries[]): ChartRow[] {
  const byDate = new Map<string, ChartRow>();
  for (const s of series) {
    for (const p of s.points) {
      const day = p.date.slice(0, 10);
      const row = byDate.get(day) ?? { date: day };
      row[`p${s.project_id}`] = p.score;
      byDate.set(day, row);
    }
  }
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
}

function TrendTooltip({ active, payload, label }: TooltipContentProps<TooltipValueType, string | number>) {
  const bg = useColorModeValue('white', 'gray.800');
  if (!active || !payload || payload.length === 0) return null;
  return (
    <Box bg={bg} borderWidth="1px" borderRadius="md" boxShadow="lg" px={3} py={2} fontSize="sm">
      <Text fontWeight="semibold" mb={1}>
        {formatDay(String(label))}
      </Text>
      {payload.map((entry) => (
        <HStack key={String(entry.dataKey)} spacing={2}>
          <Box w={2.5} h={2.5} borderRadius="full" bg={entry.color} flexShrink={0} />
          <Text flex={1}>{entry.name}</Text>
          <Text fontWeight="semibold">{entry.value}</Text>
        </HStack>
      ))}
    </Box>
  );
}

/** Score history, one line per project, with a 7/30/90-day range toggle. */
export function ScoreTrendChart({ series, days, onDaysChange, isLoading = false }: ScoreTrendChartProps) {
  const palette = useColorModeValue(SERIES_PALETTE_LIGHT, SERIES_PALETTE_DARK);
  const [axisLight, axisDark, gridLight, gridDark] = useToken('colors', ['gray.600', 'gray.400', 'gray.200', 'gray.700']);
  const axisColor = useColorModeValue(axisLight, axisDark);
  const gridColor = useColorModeValue(gridLight, gridDark);

  const withData = useMemo(
    () => (series ?? []).filter((s) => s.points.length > 0).sort((a, b) => a.project_id - b.project_id),
    [series],
  );
  const shown = withData.slice(0, MAX_SERIES);
  const hiddenCount = withData.length - shown.length;
  const rows = useMemo(() => buildRows(shown), [shown]);
  const meta: SeriesMeta[] = shown.map((s, i) => ({ key: `p${s.project_id}`, name: s.name, color: palette[i] ?? palette[0] }));

  return (
    <GlassCard hoverable={false}>
      <Flex justify="space-between" align={{ base: 'flex-start', sm: 'center' }} gap={3} mb={4} wrap="wrap">
        <Heading size="md">Score trend</Heading>
        <ButtonGroup size="sm" isAttached variant="outline" role="group" aria-label="Trend range">
          {TREND_RANGES.map((r) => (
            <MotionButton
              key={r}
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.95 }}
              variant={r === days ? 'solid' : 'outline'}
              aria-pressed={r === days}
              onClick={() => onDaysChange(r)}
            >
              {r}d
            </MotionButton>
          ))}
        </ButtonGroup>
      </Flex>

      {isLoading ? (
        <Skeleton h="300px" borderRadius="lg" />
      ) : rows.length === 0 ? (
        <Flex h="300px" align="center" justify="center" direction="column" gap={2} textAlign="center">
          <Text fontWeight="semibold">No completed scans in the last {days} days</Text>
          <Text color="text.muted" fontSize="sm">
            Run a scan on one of your projects to start tracking its score.
          </Text>
        </Flex>
      ) : (
        <>
          <Box h="300px" w="full" role="img" aria-label={`Score trend over the last ${days} days`}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
                <CartesianGrid stroke={gridColor} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tickFormatter={formatDay} stroke={axisColor} fontSize={12} tickLine={false} />
                <YAxis domain={[0, 100]} stroke={axisColor} fontSize={12} tickLine={false} />
                <Tooltip content={TrendTooltip} />
                <Legend />
                {meta.map((m) => (
                  <Line
                    key={m.key}
                    type="monotone"
                    dataKey={m.key}
                    name={m.name}
                    stroke={m.color}
                    strokeWidth={2}
                    dot={{ r: 4 }}
                    activeDot={{ r: 6 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </Box>
          {hiddenCount > 0 && (
            <Text mt={2} fontSize="sm" color="text.muted">
              +{hiddenCount} more project{hiddenCount === 1 ? '' : 's'} not shown
            </Text>
          )}
        </>
      )}
    </GlassCard>
  );
}
