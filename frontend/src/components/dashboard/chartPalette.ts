/**
 * Fixed categorical palette for per-project series (validated for CVD separation on light
 * and dark surfaces). Assigned in fixed order, never cycled: at most 8 series are drawn.
 */
export const SERIES_PALETTE_LIGHT = [
  '#2a78d6',
  '#eb6834',
  '#1baf7a',
  '#eda100',
  '#e87ba4',
  '#008300',
  '#6250d6',
  '#e34948',
] as const;

export const SERIES_PALETTE_DARK = [
  '#3987e5',
  '#d95926',
  '#199e70',
  '#c98500',
  '#d55181',
  '#008300',
  '#9085e9',
  '#e66767',
] as const;

export const MAX_SERIES = SERIES_PALETTE_LIGHT.length;

/** Selectable score-trend windows, in days. */
export const TREND_RANGES = [7, 30, 90] as const;
export type TrendRange = (typeof TREND_RANGES)[number];
