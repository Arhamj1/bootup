// Thin client for the FastAPI backend (server/api.py).

export type Mode = "hybrid" | "dense" | "bm25";

export interface Hit {
  n: number;
  id: string;
  file: string;
  name: string;
  locator: string;
  topic: string;
  source_type: string;
  ranks: Partial<Record<"dense" | "bm25", number>>;
  score: number;
  text: string;
}

export interface Status {
  auth_required: boolean;
  authorized: boolean;
  public: boolean;
  loading: boolean;
  course: string;
  key_set: boolean;
  llm_model: string;
  embedder: string;
  embedder_is_standin: boolean;
  chunks: number | null;
  course_files: number | null;
  index_error: string | null;
  examples: string[];
  modes: Mode[];
  default_k: number;
  settings: { chunk_tokens: number; overlap_pct: number; top_k_each: number; top_k_final: number; rrf_k: number };
}

export interface AskOptions {
  mode: Mode;
  k: number;
  compare_plain: boolean;
  retrieval_only: boolean;
}

export interface Turn {
  id: string;
  question: string;
  options: AskOptions;
  hits: Hit[] | null;
  answer: string;
  plain: string;
  cited: number[];
  error: string | null;
  done: boolean;
  askedAt: number;
}

export const MODE_LABEL: Record<Mode, string> = { hybrid: "Hybrid", dense: "Dense", bm25: "BM25" };
export const MODE_HELP: Record<Mode, string> = {
  hybrid: "Merges both rankings with Reciprocal Rank Fusion",
  dense: "Matches meaning, even when the wording differs",
  bm25: "Matches exact terms such as Banker's or Bakery",
};

const CODE_KEY = "bootup.access";

/** Access code for the public site (stored in this browser only). */
export function getAccessCode(): string {
  try { return localStorage.getItem(CODE_KEY) ?? ""; } catch { return ""; }
}
export function setAccessCode(code: string) {
  try { localStorage.setItem(CODE_KEY, code); } catch { /* storage blocked */ }
}

/** fetch with the access code attached (the server ignores it when no code is configured). */
function apiFetch(url: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  const code = getAccessCode();
  if (code) headers.set("X-Access-Code", code);
  return fetch(url, { ...init, headers });
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* not JSON */ }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const getStatus = () => apiFetch("/api/status").then((r) => json<Status>(r));
export const getStats = () => apiFetch("/api/stats").then((r) => json<Record<string, any>>(r));
export const getFiles = () => apiFetch("/api/files").then((r) => json<{ file: string; name: string; chunks: number }[]>(r));
export const getChunks = (file: string) =>
  apiFetch(`/api/chunks?file=${encodeURIComponent(file)}`).then((r) => json<{ locator: string; words: number; text: string }[]>(r));
export const getCompare = (q: string) =>
  apiFetch(`/api/compare?q=${encodeURIComponent(q)}`).then((r) => json<{ question: string; results: Record<Mode, Hit[]>; shared: string[] }>(r));
export const getEvalRuns = () => apiFetch("/api/eval").then((r) => json<{ runs: string[] }>(r));
export const getEvalRun = (name: string) => apiFetch(`/api/eval/${encodeURIComponent(name)}`).then((r) => json<Record<string, any>>(r));
export const rebuildIndex = () => apiFetch("/api/build", { method: "POST" }).then((r) => json<{ chunks_indexed: number; files_used: number }>(r));

type AskEvent =
  | { event: "sources"; data: { mode: Mode; hits: Hit[] } }
  | { event: "token"; data: { t: string } }
  | { event: "plain"; data: { t: string } }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: { cited: number[] } };

/** POST /api/ask and call onEvent for each server-sent event as it arrives. */
export async function streamAsk(question: string, opts: AskOptions, onEvent: (e: AskEvent) => void, signal?: AbortSignal) {
  const res = await apiFetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, ...opts }),
    signal,
  });
  if (!res.ok || !res.body) {
    await json(res);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (data) onEvent({ event, data: JSON.parse(data) } as AskEvent);
    }
  }
}
