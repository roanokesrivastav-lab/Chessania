import AnalyzeForm from "@/components/AnalyzeForm";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 py-12 text-center">
      <div className="flex max-w-md flex-col gap-6">
        <div className="space-y-2">
          <h1 className="text-4xl font-bold tracking-tight text-foreground">
            Chessania
          </h1>
          <p className="text-lg text-foreground/80">
            Free coaching report from your last 20 games — no signup.
          </p>
        </div>

        <AnalyzeForm />

        <ul className="space-y-1 text-sm text-foreground/60">
          <li>Analyzes your last 20 rapid and blitz games with Stockfish.</li>
          <li>Built for sub-1800 players who want concrete, specific advice.</li>
          <li>Reports are public — share your link with anyone.</li>
        </ul>
      </div>
    </main>
  );
}
