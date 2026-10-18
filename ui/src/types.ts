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

/** state (D22.1): up; down = was running earlier and stopped (red); off = installed, not running; absent = not set up */
export type Service = { up: boolean; ms: number | null; version?: string | null; error?: string; pid?: number;
  state?: "up" | "down" | "off" | "absent" };
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
export type ChatItem = { id: string; ts: number; kind: string; data: any };

/** K8: what went with one message (by: "pack") and what the agent read itself (by: "agent"). */
export type ReadingItem = {
  key: string; kind: "note" | "source"; title: string; ref: { uid?: string; source?: string; path?: string };
  by: "pack" | "agent"; chars: number; excerpt: string; dropped: boolean; flagged: boolean;
};
export type Briefing = {
  id: string; chat: string; ts: number; agent: string; session: string; query: string; terms: string[];
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
export type SearchHit = { path: string; ref: string; title: string; folder: string; archived: boolean; snippet: string; score: number;
  match?: "words" | "meaning" | "both"; similarity?: number };
export type SearchResult = { q: string; ms: number; results: SearchHit[]; mode?: "words" | "both" };
/** K14 (D37): meaning-based search's model and index. */
export type SemanticPanel = {
  state: "off" | "paused" | "indexing" | "ready" | "error"; reason?: string | null; installed: boolean;
  download: { state: string; done: number; total: number; error: string | null } | null;
  notes: number; documents: number; what?: string | null; done?: number; total?: number; documents_left?: number; size: number;
};
export type SourceInfo = {
  name: string; path: string; copy: string; include: string[]; files: number; indexed: number;
  last_sync: number | null; last_stats: { copied: number; unchanged: number; removed: number; private_content: number; errors: number; skipped: number } | null;
  skipped: { path: string; reason: string }[]; syncing: boolean; progress?: { done: number; total: number }; google?: boolean;
};
export type GoogleStatus = { configured: boolean; connected: boolean; client_file: string; account: string | null };
export type SourcesPanel = { sources: SourceInfo[]; google?: GoogleStatus | null };
export type SourceCollection = { dir: string; title: string; docs: number; markdown: number; folder: string; note: string | null; status: "new" | "pending" | "built" };
export type BuildResult = { proposed: number; notes: number; already: number; left_out: { path: string; reason: string }[]; not_sent: { collection: string; reason: string }[] };
export type SourceHit = { source: string; path: string; title: string; snippet: string; score: number; match?: "words" | "meaning" | "both" };
export type SourceDoc = { source: string; path: string; size: number; status: string; note: string | null; chars: number; offset: number; text: string; more: boolean };
export type Batch = {
  id: string; proposal_id: string; agent: string; summary: string; status: "applying" | "applied" | "undoing" | "undone" | "rolled_back";
  started: number; finished: number | null; undone: number | null; proposal_ids?: string[];
  auto?: string | null;            // K7: filed by the agent's trust level, not by a decision of yours
  files: { seq: number; path: string; op: "create" | "update" | "remove"; undone?: number | null }[];
};

/** K7 (D36): an agent's standing with you, and what it did. */
export type TrustLevel = "ask" | "new_notes" | "trusted";
export type AgentTrust = {
  key: string; label: string; level: TrustLevel; role: "researcher" | "librarian" | "reviewer"; config: Record<string, any>;
  record: { decided: number; approved: number; rejected: number; streak: number; auto_undone: number };
  suggest: TrustLevel | null;
};
export type ActivityEntry = { id: string; ts: number; agent: string; key: string; action: string; detail: string; ref: Record<string, any> };
export type ReviewerSettings = { provider: string; model: string | null; auto: boolean };
export type LibrarianState = { status: "idle" | "running" | "done" | "failed"; folder?: string | null; done?: number; total?: number;
  proposal?: string | null; error?: string | null; result?: string; ts?: number };
export type Verdict = { status: "queued" | "running" | "waiting" | "done" | "failed"; by?: string; drops?: Record<string, string>;
  reviewed?: number; reason?: string; error?: string };

// -- Models (D22): local engine + providers + model chat --------------------------------------------
export type Hardware = { os: string; arch: string; ram_gb: number; ram_free_gb: number; backend: string;
  gpu: { vendor: string; name: string; vram_gb: number; driver?: string } | null };
export type EngineJob = { kind: string; target: string; total: number; done: number; state: "queued" | "running" | "done" | "failed" | "cancelled"; error: string | null };
export type EngineModel = { id: string; label: string; note?: string; repo?: string; file?: string; path?: string; licence?: string;
  size: number; fit: "fits" | "tight" | "too big"; need_gb: number; installed?: boolean };
export type EnginePanel = { hardware: Hardware; binary: string | null; port: number; base_url: string;
  serving: { id: string; path: string; started: number; ready: boolean } | null; jobs: Record<string, EngineJob> };
export type EngineState = EnginePanel & { catalog: EngineModel[]; local: EngineModel[]; disabled?: boolean;
  setup?: { model: string; step: "engine" | "model" | "start" | "loading" | "ready"; error: string | null } | null };
/** W3 (D39): the one chat space. */
export type AI = { agent: string; provider: string | null; model: string | null; label: string; kind: string; where: string;
  ready?: boolean; switch_into?: boolean ; name?: string; note?: string | null; first?: boolean };
export type ThreadRow = { id: string; title: string; pinned: boolean; archived: boolean; updated: number; created: number;
  ais: string[]; current: { agent: string; label: string; model: string | null; provider?: string | null }; busy: boolean; snippet: string | null };
export type ThreadPart = { agent: string; sid: string; label: string; model: string | null; provider?: string | null; started: number; items: any[];
  error: string | null; pane: string | null; busy: boolean };
export type ChatUsage = { tokens_in: number; tokens_out: number; cost: number; plan_value?: number; billing: string[]; estimated: boolean; priced: boolean };
export type Thread = { id: string; title: string; pinned: boolean; archived: boolean; created: number; updated: number; parts: ThreadPart[]; usage?: ChatUsage };
export type ProviderInfo = { id: string; label: string; base_url: string; kind: "local" | "cloud"; key_source: string | null;
  key_present: boolean | null; models: { id: string; state: string | null }[]; error: string | null };
export type ChatSessionInfo = { id: string; title: string; provider: string; model: string; created: number; updated: number; status: "idle" | "running" };

// -- K12 digests -------------------------------------------------------------------------------------
export type DigestSection = { idx: number; chapter: string; title: string; pages: number[]; status: string; concepts: number;
  covered: number; missing: string[]; notes: string[]; error: string | null; ms: number | null; chars: number };
export type DigestJob = { id: string; source: string; path: string; title: string; provider: string; model: string;
  status: "running" | "paused" | "done" | "cancelled"; created: number; updated: number; chars: number; error: string | null;
  sections_total: number; counts: Record<string, number>; notes: number; concepts: number; covered: number;
  chapters_total: number; chapters_done: number;
  sections?: DigestSection[]; chapters?: { chapter: string; status: string; proposals: string[]; error: string | null }[] };
export type DigestPreview = { source: string; path: string; chars: number; sections: number; chapters: number;
  outline: { chapter: string; sections: string[] }[] };

export type GameModePanel = {
  mode: "always" | "ask" | "never"; state: "watching" | "asking" | "aside" | "micro"; manual: boolean;
  program: { name: string; why?: string; vram_bytes?: number } | null; since: number | null; previous: string | null;
  note: string | null; resume_in: number | null; os?: string;
  card: { name: string; vendor?: string; total_gb: number; used_gb: number } | null;
  seen: { name: string; vram_gb: number; busy: number | null }[];
  programs: Record<string, { counts?: "always" | "never"; micro?: "keep" | "pause" }>;
};

export type Panels = {
  gamemode?: GameModePanel;
  digests?: { jobs: DigestJob[] };
  engine?: EnginePanel;
  chat?: { sessions: ChatSessionInfo[] };
  board?: Board; gpu?: Gpu; health?: Health; safety?: Guard[]; sessions?: ProfileSessions[];
  inbox?: InboxItem[]; claude?: ClaudePanel; claude_usage?: Record<string, UsageWindow>;
  hermes_runs?: Record<string, { run_id: string | null; profile: string }>;
  vault?: VaultPanel;
  sources?: SourcesPanel;
  agents_trust?: { agents: AgentTrust[]; auto: Batch[]; reviewer: ReviewerSettings };
  librarian?: LibrarianState;
  semantic?: SemanticPanel;
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
