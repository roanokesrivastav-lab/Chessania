export type Platform = "chesscom" | "lichess";

export type JobState = "queued" | "running" | "done" | "error";
export type JobStage = "fetching" | "analyzing" | "coaching";
export type AnalysisMode = "standard" | "deep";

export interface AnalyzeResponse {
  job_id: string;
}

export interface Job {
  job_id: string;
  platform: Platform;
  username: string;
  state: JobState;
  stage: JobStage;
  mode: AnalysisMode;
  current_game: number;
  total_games: number;
  error_message: string | null;
  report_ready: boolean;
}

export interface EvidenceRef {
  game_url: string;
  played_at: string | null;
  opponent_rating: number | null;
  ply: number;
  move_san: string;
  detail: string;
}

export interface Link {
  label: string;
  url: string;
}

export interface Issue {
  key: string;
  headline: string;
  diagnosis: string;
  prescription: string;
  success_metric: string;
  counter_evidence: string | null;
  rating_impact: "high" | "medium" | "low";
  refresh_after: string;
  links: Link[];
  evidence: EvidenceRef[];
}

export interface Strength {
  headline: string;
  detail: string;
}

export interface OpeningRec {
  color: "white" | "black";
  name: string;
  eco_family: string;
  why: string;
  study_link: Link;
  already_plays: boolean;
}

export interface OpeningLineStat {
  color: "white" | "black";
  eco: string;
  name: string;
  games: number;
  results: WLD;
  avg_opening_eval: number;
  low_signal: boolean;
}

export interface Playstyle {
  label: "tactical" | "positional" | "balanced";
  score: number;
  explanation: string;
  components: Record<string, number>;
}

export interface PhaseStats {
  opening: number;
  middlegame: number;
  endgame: number;
}

export interface WLD {
  win: number;
  loss: number;
  draw: number;
}

export interface ColorStats {
  games: number;
  results: WLD;
  blunders_per_game: number;
  acpl_overall: number | null;
  acpl_by_phase: PhaseStats;
  worst_phase: "opening" | "middlegame" | "endgame" | null;
  opening_leak_rate: number;
  endgame_conversion: number | null;
  low_signal: boolean;
}

export interface StatsBlock {
  blunders_per_game: number;
  mistakes_per_game: number;
  acpl_overall: number;
  acpl_by_phase: PhaseStats;
  endgame_conversion: number | null;
  advantage_capitalization: number | null;
  resourcefulness: number | null;
  accuracy_trend: "improving" | "flat" | "declining" | "insufficient_data";
  per_game_acpl: number[];
  by_color: Record<string, ColorStats> | null;
}

export interface Delta {
  metric: string;
  previous: number;
  current: number;
  direction: "better" | "worse" | "flat";
}

export interface Progress {
  vs_previous: Delta[];
  vs_first: Delta[];
  previous_report_at: string;
  note: string | null;
}

export interface PlayerSummary {
  platform: Platform;
  username: string;
  rating: number | null;
  games_analyzed: number;
  date_range: string;
  time_class_mix: string;
}

export interface Report {
  schema_version: number;
  analysis_mode: AnalysisMode;
  player_summary: PlayerSummary;
  playstyle: Playstyle;
  strengths: Strength[];
  issues: Issue[];
  opening_recs: OpeningRec[];
  opening_performance: OpeningLineStat[];
  stats_block: StatsBlock;
  progress: Progress | null;
  generated_at: string;
  engine_depth: number;
}
