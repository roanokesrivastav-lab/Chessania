"use client";

import { useEffect, useRef, useState } from "react";
import { getStatInfo } from "@/lib/statInfo";

interface Props {
  id: string;
}

export default function StatExplainer({ id }: Props) {
  const info = getStatInfo(id);
  if (!info) return null;

  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    function handleClick(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handleClick);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClick);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative inline-flex items-center">
      <button
        type="button"
        aria-label={`What is ${info.term}?`}
        aria-expanded={open}
        aria-controls={`stat-explainer-${id}`}
        onClick={() => setOpen((o) => !o)}
        className="ml-1 inline-flex h-5 w-5 items-center justify-center rounded-full border border-foreground/20 text-[10px] font-semibold text-foreground/70 transition-colors hover:bg-foreground/10 hover:text-foreground focus-visible:ring-2 focus-visible:ring-offset-1"
      >
        ?
      </button>
      {open && (
        <div
          id={`stat-explainer-${id}`}
          role="region"
          aria-label={`${info.term} explanation`}
          className="absolute left-0 top-6 z-20 w-72 max-w-[calc(100vw-2rem)] rounded-lg border border-foreground/10 bg-background p-3 text-sm shadow-lg sm:w-80"
        >
          <p className="font-semibold text-foreground">{info.term}</p>
          <p className="mt-1 text-foreground/80">{info.definition}</p>
          <p className="mt-2 text-foreground/70">{info.atYourLevel}</p>
        </div>
      )}
    </div>
  );
}
