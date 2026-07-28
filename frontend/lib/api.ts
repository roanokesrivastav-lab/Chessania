import type { AnalyzeResponse, Job, Platform, Report } from "./types";

const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number | null;

  constructor(message: string, status: number | null) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

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
  return "We couldn't reach Chessania — try again in a minute.";
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new ApiError(await extractError(response), response.status);
  }
  return (await response.json()) as T;
}

function throwNetworkError(): never {
  throw new ApiError(
    "Chessania's engine room is napping — try again in a minute.",
    null
  );
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
    throwNetworkError();
  });

  return handleResponse<AnalyzeResponse>(response);
}

export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(apiUrl(`/api/jobs/${jobId}`)).catch(() => {
    throwNetworkError();
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
    throwNetworkError();
  });

  return handleResponse<Report>(response);
}
