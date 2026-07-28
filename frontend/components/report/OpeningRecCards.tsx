import type { OpeningRec } from "@/lib/types";

interface Props {
  recs: OpeningRec[];
}

export default function OpeningRecCards({ recs }: Props) {
  if (recs.length === 0) return null;

  return (
    <section>
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-foreground/60">
        Opening recommendations
      </h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {recs.map((rec) => (
          <div
            key={rec.color}
            className="rounded-lg border border-foreground/10 bg-background p-4"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold">{rec.name}</h3>
              <span className="rounded-full border border-foreground/20 px-2 py-0.5 text-xs font-semibold uppercase text-foreground/70">
                {rec.color}
              </span>
            </div>
            <p className="mt-1 text-xs text-foreground/50">{rec.eco_family}</p>
            <p className="mt-2 text-sm text-foreground/80">{rec.why}</p>
            <p className="mt-2 text-xs font-semibold text-foreground/70">
              {rec.already_plays
                ? "You already play this — deepen it."
                : "Worth trying as a new weapon."}
            </p>
            <a
              href={rec.study_link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex rounded-md bg-foreground px-3 py-1.5 text-xs font-semibold text-background transition-opacity hover:opacity-80"
            >
              {rec.study_link.label}
            </a>
          </div>
        ))}
      </div>
    </section>
  );
}
