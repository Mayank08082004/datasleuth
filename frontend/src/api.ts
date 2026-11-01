import type {
  ChatResponse,
  DatasetMeta,
  DocumentMeta,
  PreviewResponse,
  ProfileResponse,
  QualityResponse,
  ReportResponse,
} from "./types";

const KEY_STORAGE = "datasleuth_api_key";

export function getApiKey(): string {
  return localStorage.getItem(KEY_STORAGE) ?? "";
}

export function setApiKey(key: string): void {
  localStorage.setItem(KEY_STORAGE, key.trim());
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-API-Key", getApiKey());
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  listDatasets: () => request<{ datasets: DatasetMeta[] }>("/api/datasets"),
  getDataset: (id: string) => request<DatasetMeta>(`/api/datasets/${id}`),
  uploadDataset: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DatasetMeta>("/api/datasets/upload", { method: "POST", body: form });
  },
  profile: (id: string) => request<ProfileResponse>(`/api/datasets/${id}/profile`),
  preview: (id: string, page: number, pageSize = 20) =>
    request<PreviewResponse>(`/api/datasets/${id}/preview?page=${page}&page_size=${pageSize}`),
  quality: (id: string) => request<QualityResponse>(`/api/datasets/${id}/quality`),
  listDocuments: (id: string) => request<{ documents: DocumentMeta[] }>(`/api/datasets/${id}/documents`),
  uploadDocument: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentMeta>(`/api/datasets/${id}/documents`, { method: "POST", body: form });
  },
  chat: (id: string, question: string) =>
    request<ChatResponse>(`/api/datasets/${id}/chat`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
  report: (id: string) =>
    request<ReportResponse>(`/api/datasets/${id}/reports`, {
      method: "POST",
      body: JSON.stringify({ include_business_rules: true }),
    }),
  health: () => fetch("/health").then((r) => r.ok),
};
