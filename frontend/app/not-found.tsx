import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 py-12 text-center">
      <h1 className="text-3xl font-bold text-foreground">
        This page slipped off the board.
      </h1>
      <p className="text-foreground/70">
        The page you were looking for doesn&apos;t exist.
      </p>
      <Link
        href="/"
        className="rounded-lg bg-foreground px-4 py-2 font-semibold text-background transition-opacity hover:opacity-90"
      >
        Go home
      </Link>
    </main>
  );
}
