import type { AnalyzeResponse, Job, Platform, Report } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

async function extractError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Fall through to a generic message if the body isn't JSON.
  }
  return "Something went wrong reaching Chessania.";
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await extractError(response));
  }
  return (await response.json()) as T;
}

export async function analyze(
  platform: Platform,
  username: string
): Promise<AnalyzeResponse> {
  const response = await fetch(apiUrl("/api/analyze"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ platform, username }),
  }).catch(() => {
    throw new Error(
      "Chessania's engine room is napping — try again in a minute."
    );
  });

  return handleResponse<AnalyzeResponse>(response);
}

export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(apiUrl(`/api/jobs/${jobId}`)).catch(() => {
    throw new Error(
      "Chessania's engine room is napping — try again in a minute."
    );
  });

  return handleResponse<Job>(response);
}

export async function getReport(
  platform: Platform,
  username: string
): Promise<Report> {
  const response = await fetch(
    apiUrl(`/api/reports/${platform}/${username}`)
  ).catch(() => {
    throw new Error(
      "Chessania's engine room is napping — try again in a minute."
    );
  });

  return handleResponse<Report>(response);
}
