"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Chessground } from "chessground";
import type { Api } from "chessground/api";
import type { Config } from "chessground/config";
import type { Key } from "chessground/types";
import { Chess } from "chessops/chess";
import { chessgroundDests } from "chessops/compat";
import { makeFen, parseFen } from "chessops/fen";
import { makeSan } from "chessops/san";
import type { Color, NormalMove, Role, Square, SquareName } from "chessops/types";
import { makeSquare, parseSquare, squareRank } from "chessops/util";

// chessground's base CSS + the brown board theme + the cburnett piece set.
// (CSS imported from node_modules may be imported from any component.)
import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";

export interface BoardMove {
  from: SquareName;
  to: SquareName;
  promotion?: Role;
  san: string;
  fen: string;
}

export interface BoardProps {
  /** Full FEN (with the side-to-move field). Re-parsed whenever it changes. */
  fen: string;
  /** Which side sits at the bottom of the screen. */
  orientation?: "white" | "black";
  /** Called after a legal move is played: square names, SAN, and the new FEN. */
  onMove?: (move: BoardMove) => void;
  /** false → the board displays the position but nobody can move. Default true. */
  interactable?: boolean;
  /** Optional last-move highlight ([from, to]); defaults to the latest played move. */
  lastMove?: [SquareName, SquareName] | null;
  /** Optional check highlight; defaults to computing check from the position. */
  check?: boolean | "white" | "black";
  /** true → chessground binds no events at all. Init-only (per chessground's API). */
  viewOnly?: boolean;
  /** Accessible label for the board region. */
  ariaLabel?: string;
}

/**
 * Board — the ONE chessground wrapper every trainer reuses (V2-S1).
 *
 * Legal moves come from chessops (`chessgroundDests`), never from bespoke
 * piece-movement math. A user move is validated against chessops, played on a
 * local position, and reported out via `onMove` with its SAN + new FEN.
 * Promotion shows a small Q/R/B/N picker before the move is committed.
 *
 * Note: chessground wipes the element's innerHTML when it mounts, so all
 * overlay UI (the promotion picker) lives OUTSIDE the board element, as a
 * sibling positioned over it.
 */
export default function Board({
  fen,
  orientation = "white",
  onMove,
  interactable = true,
  lastMove,
  check,
  viewOnly = false,
  ariaLabel = "Chess board",
}: BoardProps) {
  const boardElRef = useRef<HTMLDivElement>(null);
  const cgRef = useRef<Api | null>(null);
  const posRef = useRef<Chess | null>(null);
  const [promotion, setPromotion] = useState<{ from: Square; to: Square } | null>(null);

  // The last move played on THIS board, so the re-sync effect (which fires
  // whenever the parent feeds a new fen back through onMove) restores the
  // highlight instead of wiping it: chessground clears lastMove when the
  // config contains a falsy lastMove, and the prop defaults to null.
  // lastFenRef holds the fen that produced that highlight, so an EXTERNAL
  // fen change (e.g. the demo's Reset) clears it instead of leaking it.
  const lastMoveRef = useRef<Key[] | undefined>(undefined);
  const lastFenRef = useRef<string | null>(null);

  // Keep the latest onMove without re-binding chessground's events.
  const onMoveRef = useRef(onMove);
  onMoveRef.current = onMove;

  /** Play a validated move on the local chessops position and report it. */
  const commitMove = useCallback(
    (pos: Chess, from: Square, to: Square, promotionRole?: Role) => {
      const cg = cgRef.current;
      if (!cg) return;
      const move: NormalMove = promotionRole
        ? { from, to, promotion: promotionRole }
        : { from, to };
      if (!pos.isLegal(move)) return; // should never happen — dests are chessops-driven
      const san = makeSan(pos, move); // SAN is computed against the pre-move position
      pos.play(move);
      const newFen = makeFen(pos.toSetup());
      const fromName = makeSquare(from);
      const toName = makeSquare(to);

      cg.set({
        fen: newFen,
        lastMove: [fromName, toName] as Key[],
        turnColor: pos.turn,
        check: pos.isCheck() ? pos.turn : false,
        movable: {
          color: interactable ? pos.turn : undefined,
          dests: interactable ? (chessgroundDests(pos) as Map<Key, Key[]>) : undefined,
          showDests: true,
          events: { after: handleAfterRef.current },
        },
      });
      lastMoveRef.current = [fromName, toName] as Key[];
      lastFenRef.current = newFen;
      setPromotion(null);
      onMoveRef.current?.({
        from: fromName,
        to: toName,
        promotion: promotionRole,
        san,
        fen: newFen,
      });
    },
    [interactable],
  );

  /** chessground calls this after the user drops a piece (already moved visually). */
  const handleAfter = useCallback(
    (orig: Key, dest: Key) => {
      const pos = posRef.current;
      if (!pos) return;
      const from = parseSquare(orig as SquareName);
      const to = parseSquare(dest as SquareName);
      const piece = pos.board.get(from);
      const lastRank = piece?.color === "white" ? 7 : 0;
      // A pawn landing on the last rank needs a promotion choice first.
      if (piece?.role === "pawn" && squareRank(to) === lastRank) {
        setPromotion({ from, to });
        return;
      }
      commitMove(pos, from, to);
    },
    [commitMove],
  );

  // Stable reference so chessground's bound events always see the latest handler.
  const handleAfterRef = useRef(handleAfter);
  handleAfterRef.current = handleAfter;

  // Mount (or viewOnly toggle): create chessground once on the board element.
  useEffect(() => {
    const el = boardElRef.current;
    if (!el) return;
    const cg = Chessground(el, {
      viewOnly,
      coordinates: true,
      animation: { enabled: true, duration: 150 },
      highlight: { lastMove: true, check: true },
      draggable: { enabled: true, showGhost: true },
      selectable: { enabled: true },
      movable: {
        showDests: true,
        events: { after: handleAfterRef.current },
      },
    });
    cgRef.current = cg;
    return () => {
      cg.destroy();
      cgRef.current = null;
    };
    // viewOnly is init-only in chessground's set(); recreate when it flips.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewOnly]);

  // Re-sync whenever the external position/orientation/options change.
  useEffect(() => {
    const cg = cgRef.current;
    if (!cg) return;
    const parsed = parseFen(fen);
    if (parsed.isErr) return;
    const setup = parsed.unwrap();
    const posResult = Chess.fromSetup(setup);
    if (posResult.isErr) return;
    const pos = posResult.unwrap();
    posRef.current = pos;

    const canMove = interactable && !viewOnly;
    // An external fen change (Reset, a trainer loading a new position) must
    // not leak the previous game's last-move highlight — or a promotion
    // picker left open over the old position.
    if (lastFenRef.current !== null && fen !== lastFenRef.current) {
      lastMoveRef.current = undefined;
      lastFenRef.current = null;
      setPromotion(null);
    }
    const config: Config = {
      fen,
      orientation,
      turnColor: pos.turn,
      check: check !== undefined ? check : pos.isCheck() ? pos.turn : false,
      // A parent-passed tuple wins; an explicit null clears the highlight;
      // absent (undefined) keeps the last move this board played (see the
      // lastMoveRef note above).
      lastMove: lastMove === undefined ? lastMoveRef.current : lastMove ?? undefined,
      movable: {
        color: canMove ? pos.turn : undefined,
        dests: canMove ? (chessgroundDests(pos) as Map<Key, Key[]>) : undefined,
        showDests: true,
        events: { after: handleAfterRef.current },
      },
    };
    cg.set(config);
  }, [fen, orientation, interactable, viewOnly, lastMove, check]);

  const pickPromotion = (role: Role) => {
    const pos = posRef.current;
    if (!pos || !promotion) return;
    commitMove(pos, promotion.from, promotion.to, role);
  };

  const cancelPromotion = () => {
    const cg = cgRef.current;
    const pos = posRef.current;
    setPromotion(null);
    // The pawn was already pushed visually — put it back with the pre-move FEN.
    if (cg && pos) cg.set({ fen: makeFen(pos.toSetup()) });
  };

  return (
    <div className="w-full max-w-[560px]">
      <div className="relative aspect-square w-full">
        <div
          ref={boardElRef}
          role="group"
          aria-label={ariaLabel}
          tabIndex={0}
          className="h-full w-full outline-none focus-visible:ring-2 focus-visible:ring-gold/60"
        />
        {promotion && (
          <PromotionPicker
            color={posRef.current?.board.get(promotion.from)?.color ?? "white"}
            onPick={pickPromotion}
            onCancel={cancelPromotion}
          />
        )}
      </div>
    </div>
  );
}

function PromotionPicker({
  color,
  onPick,
  onCancel,
}: {
  color: Color;
  onPick: (role: Role) => void;
  onCancel: () => void;
}) {
  const roles: { role: Role; glyph: string }[] = [
    { role: "queen", glyph: color === "white" ? "♕" : "♛" },
    { role: "rook", glyph: color === "white" ? "♖" : "♜" },
    { role: "bishop", glyph: color === "white" ? "♗" : "♝" },
    { role: "knight", glyph: color === "white" ? "♘" : "♞" },
  ];

  // Escape cancels the promotion.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div
      role="dialog"
      aria-label="Choose a promotion piece"
      className="absolute inset-0 z-10 flex items-center justify-center"
    >
      <button
        type="button"
        aria-label="Cancel promotion"
        onClick={onCancel}
        className="absolute inset-0 cursor-pointer bg-bg/50"
      />
      <div className="relative flex gap-2 rounded-[14px] border border-border bg-surface p-2 shadow-lg">
        {roles.map(({ role, glyph }) => (
          <button
            key={role}
            type="button"
            aria-label={`Promote to ${role}`}
            onClick={() => onPick(role)}
            className="flex h-12 w-12 items-center justify-center rounded-lg border border-border bg-surface-2 text-2xl text-gold transition-colors hover:border-gold hover:bg-surface-3 focus-visible:outline-2 focus-visible:outline-gold"
          >
            {glyph}
          </button>
        ))}
      </div>
    </div>
  );
}
