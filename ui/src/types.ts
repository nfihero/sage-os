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

export type Panels = {
  board?: Board; gpu?: Gpu; health?: Health; safety?: Guard[]; sessions?: ProfileSessions[];
  inbox?: InboxItem[]; claude?: ClaudePanel; claude_usage?: Record<string, UsageWindow>;
  hermes_runs?: Record<string, { run_id: string | null; profile: string }>;
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
