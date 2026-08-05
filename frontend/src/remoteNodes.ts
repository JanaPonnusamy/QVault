export interface RemoteNode {
  id: string;
  name: string;
  baseUrl: string;
}

const KEY = "qvault_remote_nodes";

export function getRemoteNodes(): RemoteNode[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveRemoteNodes(nodes: RemoteNode[]): void {
  localStorage.setItem(KEY, JSON.stringify(nodes));
}

export function addRemoteNode(name: string, baseUrl: string): RemoteNode[] {
  const nodes = getRemoteNodes();
  const cleanedUrl = baseUrl.trim().replace(/\/$/, "");
  nodes.push({ id: crypto.randomUUID(), name: name.trim(), baseUrl: cleanedUrl });
  saveRemoteNodes(nodes);
  return nodes;
}

export function removeRemoteNode(id: string): RemoteNode[] {
  const nodes = getRemoteNodes().filter((n) => n.id !== id);
  saveRemoteNodes(nodes);
  return nodes;
}
