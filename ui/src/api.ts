/** Write calls carry X-Sage-OS; the hub refuses writes without it (CSRF guard). */
export async function post<T = any>(path: string, body: unknown = {}): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Sage-OS": "1" },
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ?? r.statusText);
  return data as T;
}

export async function get<T = any>(path: string): Promise<T> {
  const r = await fetch(path);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ?? r.statusText);
  return data as T;
}

/** Live chat frames from the hub socket, fanned out to whichever pane is showing that chat. */
export type ChatFrame = { pane: string; op: string; [k: string]: any };
const listeners = new Set<(f: ChatFrame) => void>();
export function onChat(fn: (f: ChatFrame) => void) {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}
export function emitChat(f: ChatFrame) {
  listeners.forEach((fn) => fn(f));
}
