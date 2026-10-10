export const NAME_MAX_LENGTH = 100;
export const BRANCH_MAX_LENGTH = 100;

export function getNameError(name: string): string | null {
  const value = name.trim();
  if (value.length === 0) return 'Project name is required.';
  if (value.length > NAME_MAX_LENGTH) return `Project name must be at most ${NAME_MAX_LENGTH} characters.`;
  return null;
}

/** Branch is optional; when given it must look like a git ref name (no spaces, no "..", no leading "-"). */
export function getBranchError(branch: string): string | null {
  const value = branch.trim();
  if (value.length === 0) return null;
  if (value.length > BRANCH_MAX_LENGTH) return `Branch must be at most ${BRANCH_MAX_LENGTH} characters.`;
  if (!/^[\w./-]+$/.test(value) || value.includes('..') || value.startsWith('-') || value.startsWith('/')) {
    return 'Enter a valid branch name, e.g. main or release/1.0.';
  }
  return null;
}
