export type Task = {
  id: string; title: string; assignee: string | null; status: string; priority: number;
  created_at: number; started_at?: number | null; completed_at?: number | null;
  model_override?: string | null; block_kind?: string | null; consecutive_failures?: number;
  last_heartbeat_at?: number | null; current_run_id?: number | null; created_by?: string | null;
};
export type Board = { tasks: Task[]; archived: number; links: { parent_id: string; child_id: string }[] };

export type ModelInfo = { id: string; state: string; ctx: string | null; n_cpu_moe: string | null; offload: string | null };
export type Gpu = {
  gpu: { name: string; vram_used_mb: number; vram_total_mb: number; util_pct: number; temp_c: number; power_w: number } | null;
  ram: { total_gb: number; used_gb: number; llama_gb: number; pct: number } | null;
  models: ModelInfo[]; active: ModelInfo[]; guardian: ModelInfo[]; router_error: string | null; ts: number;
};

export type Service = { up: boolean; ms: number | null; version?: string | null; error?: string; pid?: number };
export type Health = Record<"gateway" | "router" | "sidecar", Service>;

export type Guard = {
  gate: "guardian" | "write-guard"; event: string; tool: string | null; ts: number; detail: string;
  reason: string | null; error: string | null; ms: number | null; fail_closed: boolean | null;
};

export type Session = {
  id: string; source: string; title: string | null; model: string | null; started_at: number;
  ended_at?: number | null; last_activity_at?: number | null; last_activity_description?: string | null;
  message_count?: number; tool_call_count?: number; input_tokens?: number; output_tokens?: number;
  pinned?: number; archived?: number; parent_session_id?: string | null;
};
export type ProfileSessions = { profile: string; label?: string; pinned: boolean; total: number; sessions: Session[] };

export type HubEvent = { id: number | null; ts: number; kind: string; source: string; type: string; data: any };
export type Smoke = { adapter: string; check: string; ok: boolean; detail: string };

export type InboxItem = {
  id: string; source: "claude" | "hermes" | "kanban" | string; title: string; detail: string;
  choices: string[]; context: Record<string, any>; created: number;
};
export type UsageWindow = { utilization: number | null; status: string; resets_at: number | null; seen: number };
export type ClaudeSessionInfo = {
  id: string; title: string; cwd: string; model: string | null; sdk_session_id: string | null;
  created: number; updated: number; turns: number; status: "idle" | "running" | "waiting" | "error"; pending: number;
};
export type ClaudePanel = { sessions: ClaudeSessionInfo[]; cli: string | null; workspaces: string[]; logged_in: boolean | null };
export type ChatItem = { id: number | string; ts: number; kind: string; data: any };

/** K8: what went with one message (by: "pack") and what the agent read itself (by: "agent"). */
export type ReadingItem = {
  key: string; kind: "note" | "source"; title: string; ref: { uid?: string; source?: string; path?: string };
  by: "pack" | "agent"; chars: number; excerpt: string; dropped: boolean; flagged: boolean;
};
export type Briefing = {
  id: number; chat: string; ts: number; agent: string; session: string; query: string; terms: string[];
  items: ReadingItem[]; corrections: { key: string; kind: string; title: string }[];
};
export type BriefingState = { settings: { chat: string; enabled: boolean; drops: string[] }; briefings: Briefing[] };

export type NoteLink = { uid: string; title: string | null };
export type NoteMeta = {
  ref: string; path: string; folder: string; title: string; uid: string | null; type: string | null;
  status: string | null; origin: string | null; agent: string | null; source: string | null; created: string | null; updated: string | null;
  tags: string[]; links: NoteLink[]; archived: boolean; problems: string[]; sensitive: string | null; size: number; mtime: number;
};
export type NoteFull = NoteMeta & { frontmatter: Record<string, any>; body: string; text: string };   // text: the whole file
export type VaultPanel = { root: string; exists: boolean; count: number; problems: number; folders: string[]; notes: NoteMeta[]; indexed?: number };
export type SearchHit = { path: string; ref: string; title: string; folder: string; archived: boolean; snippet: string; score: number };
export type SearchResult = { q: string; ms: number; results: SearchHit[] };
export type SourceInfo = {
  name: string; path: string; copy: string; include: string[]; files: number; indexed: number;
  last_sync: number | null; last_stats: { copied: number; unchanged: number; removed: number; private_content: number; errors: number; skipped: number } | null;
  skipped: { path: string; reason: string }[]; syncing: boolean; progress?: { done: number; total: number }; google?: boolean;
};
export type GoogleStatus = { configured: boolean; connected: boolean; client_file: string; account: string | null };
export type SourcesPanel = { sources: SourceInfo[]; google?: GoogleStatus | null };
export type SourceCollection = { dir: string; title: string; docs: number; markdown: number; folder: string; note: string | null; status: "new" | "pending" | "built" };
export type BuildResult = { proposed: number; notes: number; already: number; left_out: { path: string; reason: string }[]; not_sent: { collection: string; reason: string }[] };
export type SourceHit = { source: string; path: string; title: string; snippet: string; score: number };
export type SourceDoc = { source: string; path: string; size: number; status: string; note: string | null; chars: number; offset: number; text: string; more: boolean };
export type Batch = {
  id: number; proposal_id: string; agent: string; summary: string; status: "applying" | "applied" | "undoing" | "undone" | "rolled_back";
  started: number; finished: number | null; undone: number | null; files: { path: string; op: "create" | "update" | "remove" }[];
};

export type Panels = {
  board?: Board; gpu?: Gpu; health?: Health; safety?: Guard[]; sessions?: ProfileSessions[];
  inbox?: InboxItem[]; claude?: ClaudePanel; claude_usage?: Record<string, UsageWindow>;
  hermes_runs?: Record<string, { run_id: string | null; profile: string }>;
  vault?: VaultPanel;
  sources?: SourcesPanel;
};

export type TaskDetail = {
  task: Task & { body?: string; result?: string; workspace_path?: string; last_failure_error?: string };
  runs: { id: number; status: string; outcome: string | null; profile: string | null; started_at: number;
          ended_at: number | null; summary: string | null; error: string | null }[];
  events: { id: number; run_id: number | null; kind: string; payload: any; created_at: number }[];
  heartbeats: Record<string, number>;
  comments: { author: string; body: string; created_at: number }[];
  parents: string[]; children: string[];
};
