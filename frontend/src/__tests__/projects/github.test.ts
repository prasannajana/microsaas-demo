import { describe, expect, it } from 'vitest';
import { getRepoUrlError, isValidGitHubRepoUrl, normalizeRepoUrl, repoNameFromUrl } from '../../lib/github';

describe('lib/github', () => {
  it('normalizes whitespace, trailing slashes, .git and host case', () => {
    expect(normalizeRepoUrl('  https://github.com/owner/repo/  ')).toBe('https://github.com/owner/repo');
    expect(normalizeRepoUrl('https://github.com/owner/repo.git')).toBe('https://github.com/owner/repo');
    expect(normalizeRepoUrl('https://github.com/owner/repo.git/')).toBe('https://github.com/owner/repo');
    expect(normalizeRepoUrl('HTTPS://GitHub.com/Owner/Repo')).toBe('https://github.com/Owner/Repo');
  });

  it('accepts valid GitHub repo URLs', () => {
    expect(isValidGitHubRepoUrl('https://github.com/owner/repo')).toBe(true);
    expect(isValidGitHubRepoUrl('https://github.com/my-org/my.repo_name.git')).toBe(true);
    expect(isValidGitHubRepoUrl(' https://github.com/a/b/ ')).toBe(true);
  });

  it('rejects non-GitHub and malformed URLs', () => {
    expect(isValidGitHubRepoUrl('')).toBe(false);
    expect(isValidGitHubRepoUrl('http://github.com/owner/repo')).toBe(false);
    expect(isValidGitHubRepoUrl('https://gitlab.com/owner/repo')).toBe(false);
    expect(isValidGitHubRepoUrl('git@github.com:owner/repo.git')).toBe(false);
    expect(isValidGitHubRepoUrl('https://github.com/owner')).toBe(false);
    expect(isValidGitHubRepoUrl('https://github.com/owner/repo/tree/main')).toBe(false);
    expect(isValidGitHubRepoUrl('https://github.com/owner/repo?x=1')).toBe(false);
    expect(isValidGitHubRepoUrl('https://github.com.evil.com/owner/repo')).toBe(false);
  });

  it('derives the repo name for auto-fill', () => {
    expect(repoNameFromUrl('https://github.com/owner/cool-repo.git')).toBe('cool-repo');
    expect(repoNameFromUrl('not a url')).toBeNull();
  });

  it('returns helpful error messages', () => {
    expect(getRepoUrlError('')).toMatch(/required/i);
    expect(getRepoUrlError('https://gitlab.com/a/b')).toMatch(/only github/i);
    expect(getRepoUrlError('git@github.com:a/b.git')).toMatch(/ssh/i);
    expect(getRepoUrlError('https://github.com/a/b')).toBeNull();
  });
});
