export const REPO_OWNER = 'nadavelyashiv';
export const REPO_NAME = 'yad2-scraper';
export const BRANCH = 'main';

export async function fetchDirectoryContents(path: string, token?: string) {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `token ${token}`;

  const res = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}?ref=${BRANCH}`, {
    headers,
  });
  if (!res.ok) throw new Error(`Failed to fetch ${path}`);
  return res.json();
}

export async function fetchGitTree(token?: string) {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `token ${token}`;

  const res = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/git/trees/${BRANCH}?recursive=1`, {
    headers,
  });
  if (!res.ok) throw new Error(`Failed to fetch git tree`);
  return res.json();
}

export async function fetchFileContent(path: string, token?: string) {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `token ${token}`;

  const res = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}?ref=${BRANCH}`, {
    headers,
  });
  if (!res.ok) throw new Error(`Failed to fetch file ${path}`);
  const data = await res.json();
  const content = decodeURIComponent(escape(atob(data.content)));
  return { sha: data.sha, content };
}

export async function commitFile(path: string, content: string, sha: string, message: string, token: string) {
  const headers = {
    Authorization: `token ${token}`,
    'Content-Type': 'application/json',
  };

  // Convert string to base64 safely (handles unicode)
  const encodedContent = btoa(unescape(encodeURIComponent(content)));

  const res = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify({
      message,
      content: encodedContent,
      sha,
      branch: BRANCH,
    }),
  });

  if (!res.ok) {
    const errorData = await res.json();
    throw new Error(`Failed to commit: ${errorData.message}`);
  }
  return res.json();
}
