import type { Strength } from "@/lib/types";

interface Props {
  strengths: Strength[];
}

export default function StrengthCard({ strengths }: Props) {
  if (strengths.length === 0) {
    return (
      <div className="rounded-lg border border-foreground/10 bg-foreground/5 p-4 text-sm text-foreground/70">
        No standout strength surfaced this time — keep at it and one will show up soon.
      </div>
    );
  }

  const strength = strengths[0];

  return (
    <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
      <h2 className="text-sm font-bold uppercase tracking-wide text-amber-800 dark:text-amber-200">
        Strength
      </h2>
      <p className="mt-1 text-lg font-semibold text-amber-900 dark:text-amber-100">
        {strength.headline}
      </p>
      <p className="mt-1 text-amber-800/80 dark:text-amber-100/80">
        {strength.detail}
      </p>
    </section>
  );
}
