/**
 * V2-S7: Report → trainer routing map.
 *
 * This is the CODE mirror of CHESSANIA_V2_ROADMAP.md Appendix V2-3.
 * When that appendix changes, update this map too so the two specs
 * don't silently drift apart.
 *
 * Every issue key NOT listed here gets NO "Train this" button — there
 * is no live trainer destination for it yet (endgame self-tests are a
 * future phase, opening/time-management keys have no trainer in v2).
 */

export interface TrainerRoute {
  /** The trainer route segment (e.g., "retry", "preventer", "convert"). */
  trainer: "retry" | "preventer" | "convert";
  /** The position-bank category this trainer drills. */
  category: string;
}

const ROUTING_MAP: Record<string, TrainerRoute> = {
  // blunder-family → retry (blunder positions)
  hung_pieces: { trainer: "retry", category: "blunder" },
  blunder_rate: { trainer: "retry", category: "blunder" },
  tilt: { trainer: "retry", category: "blunder" },

  // missed saves → preventer (danger positions)
  missed_saves: { trainer: "preventer", category: "danger" },

  // advantage capitalization → convert (unconverted positions)
  advantage_capitalization: { trainer: "convert", category: "unconverted" },
};

/**
 * Return the trainer + category for a given issue key, or null if no
 * live trainer exists for that key yet.
 *
 * The null keys (no button rendered):
 *   - All opening keys (opening_leak, opening_general, opening_variation)
 *   - All time-management keys (rushed_blunders, time_trouble_collapse,
 *     dawdling, blitz_gap)
 *   - overextension, late_collapse, endgame_conversion
 */
export function trainerForIssue(key: string): TrainerRoute | null {
  return ROUTING_MAP[key] ?? null;
}
