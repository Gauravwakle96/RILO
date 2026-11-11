import type { Session } from "../types";

let csrfToken = "";
let sessionPromise: Promise<Session> | null = null;

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function readResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      body.error?.message ??
      (typeof body.detail === "string"
        ? body.detail
        : Array.isArray(body.detail)
          ? body.detail.map((item: { msg: string }) => item.msg).join("; ")
          : `Request failed (${response.status}).`);
    throw new ApiError(
      message,
      response.status,
      body.error?.code ?? "request_failed",
    );
  }
  return response.json() as Promise<T>;
}

export function session(): Promise<Session> {
  if (!sessionPromise) {
    sessionPromise = fetch("/api/v1/session", {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(readResponse<Session>)
      .then((value) => {
        csrfToken = value.csrf_token;
        return value;
      })
      .catch((error) => {
        sessionPromise = null;
        throw error;
      });
  }
  return sessionPromise;
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  await session();
  const method = options.method ?? "GET";
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body && !headers.has("Content-Type"))
    headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase()))
    headers.set("X-CSRF-Token", csrfToken);
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if ([401, 403].includes(response.status)) {
    sessionPromise = null;
    csrfToken = "";
  }
  return readResponse<T>(response);
}

export function post<T>(
  path: string,
  body: unknown,
  idempotencyKey?: string,
): Promise<T> {
  return api<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
  });
}

export async function downloadReport(
  id: string,
  format: "json" | "csv",
): Promise<void> {
  await session();
  const response = await fetch(
    `/api/v1/experiments/${encodeURIComponent(id)}/report?format=${format}`,
    { credentials: "same-origin" },
  );
  if (!response.ok) {
    await readResponse(response);
    return;
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `rilo-${id}.${format}`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}

export async function downloadEvaluation(
  id: string,
  format: "pdf" | "md" | "json" | "csv",
): Promise<void> {
  await session();
  const response = await fetch(
    `/api/v1/workspace/evaluations/${encodeURIComponent(id)}/report?format=${format}`,
    { credentials: "same-origin" },
  );
  if (!response.ok) {
    await readResponse(response);
    return;
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `rilo-${id}.${format}`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function downloadConversation(id: string): Promise<void> {
  await session();
  const response = await fetch(
    `/api/v1/workspace/conversations/${encodeURIComponent(id)}/export`,
    { credentials: "same-origin" },
  );
  if (!response.ok) {
    await readResponse(response);
    return;
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `rilo-${id}.json`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
