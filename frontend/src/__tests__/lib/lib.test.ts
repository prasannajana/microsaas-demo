import { AxiosError } from 'axios';
import type { Query } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { formatDate, formatDateTime as adminDateTime, formatFailureRate } from '../../components/admin/format';
import { countBySeverity, formatDateTime, formatRelativeTime, groupFindingsByCategory, shortSha } from '../../components/projects/format';
import { getBranchError, getNameError } from '../../components/projects/validation';
import { isActiveScanStatus, scanRefetchInterval, SCAN_POLL_INTERVAL_MS } from '../../hooks/useScans';
import { getErrorMessage } from '../../lib/errors';
import { queryClient } from '../../lib/queryClient';
import { clearTokens, getAccessToken, hasTokens, setTokens } from '../../lib/tokens';
import type { ScanDetail } from '../../types';
import { httpError, makeFinding } from '../fixtures';

describe('getErrorMessage', () => {
  it('uses a FastAPI string detail', () => {
    expect(getErrorMessage(httpError(409, 'Email already registered'))).toBe('Email already registered');
  });

  it('joins validation error messages', () => {
    const err = httpError(422, [{ msg: 'field required', loc: ['body', 'email'] }, { msg: 'too short' }, 'junk', { loc: [] }]);
    expect(getErrorMessage(err)).toBe('field required; too short');
  });

  it('falls back for 429 and generic HTTP errors without detail', () => {
    expect(getErrorMessage(httpError(429, ''))).toBe('Too many requests. Please wait and try again.');
    expect(getErrorMessage(httpError(500, []))).toBe('Request failed with status code 500');
  });

  it('reports network errors (no response)', () => {
    expect(getErrorMessage(new AxiosError('Network Error'))).toBe('Unable to reach the server. Check your connection.');
  });

  it('handles plain errors, strings and unknown values', () => {
    expect(getErrorMessage(new Error('boom'))).toBe('boom');
    expect(getErrorMessage('text')).toBe('text');
    expect(getErrorMessage(42, 'fallback')).toBe('fallback');
    expect(getErrorMessage(new Error(''))).toBe('Something went wrong. Please try again.');
  });
});

describe('tokens', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it('round-trips and clears tokens', () => {
    setTokens('a', 'r');
    expect(hasTokens()).toBe(true);
    clearTokens();
    expect(hasTokens()).toBe(false);
  });

  it('survives storage being unavailable', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceeded');
    });
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });
    expect(() => setTokens('a', 'r')).not.toThrow();
    expect(getAccessToken()).toBeNull();
    expect(() => clearTokens()).not.toThrow();
  });
});

describe('queryClient retry policy', () => {
  const retry = queryClient.getDefaultOptions().queries?.retry as (n: number, e: unknown) => boolean;

  it('never retries 4xx', () => {
    expect(retry(0, httpError(404))).toBe(false);
    expect(retry(0, httpError(401))).toBe(false);
  });

  it('retries 5xx / network errors up to twice', () => {
    expect(retry(0, httpError(503))).toBe(true);
    expect(retry(1, new Error('net'))).toBe(true);
    expect(retry(2, httpError(503))).toBe(false);
  });
});

describe('scan polling helpers', () => {
  it.each([
    ['queued', true],
    ['running', true],
    ['completed', false],
    ['failed', false],
    [undefined, false],
  ] as const)('isActiveScanStatus(%s) = %s', (status, expected) => {
    expect(isActiveScanStatus(status)).toBe(expected);
  });

  it('polls every 2s only while active', () => {
    const q = (status: ScanDetail['status'] | undefined) => ({ state: { data: status ? { status } : undefined } }) as unknown as Query<ScanDetail, Error>;
    expect(scanRefetchInterval(q('running'))).toBe(SCAN_POLL_INTERVAL_MS);
    expect(scanRefetchInterval(q('completed'))).toBe(false);
    expect(scanRefetchInterval(q(undefined))).toBe(false);
  });
});

describe('formatters and validation', () => {
  const now = new Date('2026-10-10T12:00:00Z');

  it('formats relative times', () => {
    expect(formatRelativeTime(null)).toBe('Never');
    expect(formatRelativeTime('not a date')).toBe('Never');
    expect(formatRelativeTime('2026-10-10T11:59:50Z', 'Never', now)).toBe('just now');
    expect(formatRelativeTime('2026-10-10T09:00:00Z', 'Never', now)).toMatch(/3 hours ago/);
    expect(formatRelativeTime('2026-10-08T12:00:00Z', 'Never', now)).toMatch(/2 days ago/);
  });

  it('formats dates, SHAs and failure rate', () => {
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateTime('bad')).toBe('—');
    expect(formatDateTime('2026-10-10T12:00:00Z')).not.toBe('—');
    expect(shortSha('abcdef1234')).toBe('abcdef1');
    expect(shortSha(null)).toBeNull();
    expect(adminDateTime(null)).toBe('—');
    expect(adminDateTime('garbage')).toBe('garbage');
    expect(formatDate(undefined)).toBe('—');
    expect(formatDate('garbage')).toBe('garbage');
    expect(formatDate('2026-10-10T00:00:00Z')).not.toBe('—');
    expect(formatFailureRate(0.1234)).toBe('12.3%');
  });

  it('groups findings by category in a stable order, sorted by severity', () => {
    const groups = groupFindingsByCategory([
      makeFinding({ id: 1, category: 'testing', severity: 'low', title: 'b' }),
      makeFinding({ id: 2, category: 'documentation', severity: 'medium', title: 'z' }),
      makeFinding({ id: 3, category: 'testing', severity: 'critical', title: 'a' }),
    ]);
    expect(groups.map((g) => g.label)).toEqual(['Documentation', 'Testing']);
    expect(groups[1]?.findings.map((f) => f.id)).toEqual([3, 1]);
    expect(countBySeverity([makeFinding({ severity: 'low' }), makeFinding({ severity: 'low' })])).toEqual({
      critical: 0,
      high: 0,
      medium: 0,
      low: 2,
    });
  });

  it('validates project name and branch', () => {
    expect(getNameError('  ')).toBe('Project name is required.');
    expect(getNameError('x'.repeat(101))).toMatch(/at most 100/);
    expect(getNameError('ok')).toBeNull();
    expect(getBranchError('')).toBeNull();
    expect(getBranchError('release/1.0')).toBeNull();
    expect(getBranchError('b'.repeat(101))).toMatch(/at most 100/);
    for (const bad of ['-x', '/x', 'a..b', 'has space', 'semi;colon']) {
      expect(getBranchError(bad)).toMatch(/valid branch/);
    }
  });
});
