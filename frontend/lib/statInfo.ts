export type StatInfo = {
  term: string;
  definition: string;
  atYourLevel: string;
};

export const statInfo: Record<string, StatInfo> = {
  acpl: {
    term: "Average Centipawn Loss",
    definition:
      "ACPL measures how far your moves stray from the engine's best choice, on average. A centipawn is 1/100 of a pawn, so 100 ACPL is like dropping one pawn's worth of advantage every few moves.",
    atYourLevel:
      "Sub-1800 players often sit between 50-90 ACPL. If yours is under 60, you're keeping the position under control.",
  },
  acpl_phase: {
    term: "Phase ACPL",
    definition:
      "The same Average Centipawn Loss, but split into opening, middlegame, and endgame. It shows which part of the game is costing you the most.",
    atYourLevel:
      "Many sub-1800 players are weakest in the endgame. If one phase is much higher than the others, that's your cheapest improvement.",
  },
  blunders_per_game: {
    term: "Blunders per game",
    definition:
      "A blunder is a move that gives away a winning position or turns a drawn position into a lost one. This is the average across the games we analyzed.",
    atYourLevel:
      "Aim for fewer than one blunder per game. One big blunder is usually the fastest way a sub-1800 game is decided.",
  },
  mistakes_per_game: {
    term: "Mistakes per game",
    definition:
      "A mistake is a smaller inaccuracy that hands your opponent an advantage. Less damaging than a blunder, but they add up fast.",
    atYourLevel:
      "Sub-1800 players often make 3-5 mistakes per game. Cutting that by one or two per game is a reliable path to a higher rating.",
  },
  endgame_conversion: {
    term: "Endgame conversion",
    definition:
      "How often you turn a winning or drawn endgame into the result you should get. Higher is better.",
    atYourLevel:
      "At your level, converting around 60% of good endgames is solid. If this number is below 50%, studying basic king-and-pawn endings will pay off quickly.",
  },
  advantage_capitalization: {
    term: "Advantage conversion",
    definition:
      "How often you convert a game after reaching a winning advantage (about +3 pawns or more) at any point. Higher is better.",
    atYourLevel:
      "Sub-1800 players often reach a winning position but still lose. If this is below 60%, the problem is usually tactics or time management, not the endgame itself.",
  },
  opening_leak_rate: {
    term: "Opening leak rate",
    definition:
      "The share of your games where you leave the opening with a clearly worse position. Lower is better.",
    atYourLevel:
      "Sub-1800 players often leak points in the first 10 moves. If this is above 35%, tightening your openings is high-value work.",
  },
  accuracy_trend: {
    term: "Accuracy trend",
    definition:
      "A directional read on whether your recent games are more or less accurate than your older ones.",
    atYourLevel:
      "Trends are noisy; one good week doesn't mean you're a master. Still, a steady 'improving' arrow over 20+ games is a good sign.",
  },
  playstyle: {
    term: "Playstyle",
    definition:
      "A label for the overall shape of your games: tactical (lots of attacks and complications), positional (quiet maneuvering and structure), or balanced.",
    atYourLevel:
      "Playstyle isn't good or bad by itself. Use it as a clue: if you're 'tactical' but losing in quiet positions, add positional drills.",
  },
};

export function getStatInfo(id: string): StatInfo | undefined {
  return statInfo[id];
}
