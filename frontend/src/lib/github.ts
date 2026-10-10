/**
 * GitHub repository URL helpers. Mirrors the backend `repo_url` validator:
 * strip whitespace, trailing `/` and `.git`, lowercase the host, then match
 * `^https://github\.com/[\w.-]+/[\w.-]+$`.
 */

export const GITHUB_URL_RE = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+$/;

const HOST_PREFIX_RE = /^https:\/\/github\.com(?=\/|$)/i;

/** Normalize a user-entered repository URL the same way the backend does. */
export function normalizeRepoUrl(raw: string): string {
  let url = raw.trim();
  url = url.replace(/\/+$/, '');
  if (url.toLowerCase().endsWith('.git')) {
    url = url.slice(0, -4);
  }
  url = url.replace(/\/+$/, '');
  return url.replace(HOST_PREFIX_RE, 'https://github.com');
}

/** True when the URL (after normalization) is a public-style https GitHub repo URL. */
export function isValidGitHubRepoUrl(raw: string): boolean {
  return GITHUB_URL_RE.test(normalizeRepoUrl(raw));
}

/** "owner/repo" for a valid GitHub URL, otherwise null. */
export function repoSlugFromUrl(raw: string): string | null {
  const url = normalizeRepoUrl(raw);
  if (!GITHUB_URL_RE.test(url)) return null;
  return url.slice('https://github.com/'.length);
}

/** Repository name (last path segment) for auto-filling the project name, or null. */
export function repoNameFromUrl(raw: string): string | null {
  const slug = repoSlugFromUrl(raw);
  if (!slug) return null;
  const name = slug.split('/')[1];
  return name && name.length > 0 ? name : null;
}

/** Human-readable validation message for the repo URL field, or null when valid. */
export function getRepoUrlError(raw: string): string | null {
  const value = raw.trim();
  if (value.length === 0) return 'Repository URL is required.';
  if (/^git@/i.test(value)) return 'SSH URLs are not supported. Use the https://github.com/owner/repo form.';
  if (/^http:\/\//i.test(value)) return 'Use https:// — for example https://github.com/owner/repo.';
  if (!/^https:\/\/github\.com\//i.test(value)) {
    return 'Only GitHub repositories are supported (https://github.com/owner/repo).';
  }
  if (!isValidGitHubRepoUrl(value)) {
    return 'Enter a repository URL in the form https://github.com/owner/repo.';
  }
  return null;
}
