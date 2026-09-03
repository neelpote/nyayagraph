import type {
  AIBrief,
  AccessGrant,
  AuditEvent,
  CaseRecord,
  EvidenceListItem,
  GraphData,
  IntegrationStatus,
  MerkleResult,
  Passport,
  Session,
  TimelineEvent,
  UploadResult,
} from "./types";
import { clearSession, getSession } from "./auth";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function throwResponseError(response: Response): Promise<never> {
  const hadSession = Boolean(getSession());
  const body = await response.json().catch(() => ({}));
  const sessionEnded =
    response.status === 401 ||
    (response.status === 403 && body.detail === "Account is unavailable");
  if (sessionEnded && hadSession && typeof window !== "undefined") {
    clearSession();
    window.location.replace("/login?reason=session_expired");
  }
  throw new Error(
    body.detail || body.message || `Request failed (${response.status})`,
  );
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const session = getSession();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (session?.accessToken)
    headers.set("Authorization", `Bearer ${session.accessToken}`);
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) await throwResponseError(response);
  return response.json() as Promise<T>;
}

async function requestBlob(path: string): Promise<Blob> {
  const session = getSession();
  const response = await fetch(`${API_URL}${path}`, {
    headers: session?.accessToken
      ? { Authorization: `Bearer ${session.accessToken}` }
      : {},
  });
  if (!response.ok) await throwResponseError(response);
  return response.blob();
}

export const api = {
  login: (email: string, password: string) =>
    request<Session>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  cases: () => request<CaseRecord[]>("/cases"),
  createCase: (input: { caseNumber: string; title: string; description: string; caseType: string; jurisdiction: string; firNumber: string; policeStation: string; classificationLevel: number }) =>
    request<{ id: string; caseNumber: string; status: string }>("/cases", { method: "POST", body: JSON.stringify({ case_number: input.caseNumber, title: input.title, description: input.description, case_type: input.caseType, jurisdiction: input.jurisdiction, fir_number: input.firNumber, police_station: input.policeStation, classification_level: input.classificationLevel }) }),
  case: (caseNumber: string) =>
    request<CaseRecord>(`/cases/${encodeURIComponent(caseNumber)}`),
  timeline: (caseNumber: string) =>
    request<TimelineEvent[]>(
      `/cases/${encodeURIComponent(caseNumber)}/timeline`,
    ),
  graph: (caseNumber: string) =>
    request<GraphData>(`/cases/${encodeURIComponent(caseNumber)}/graph`),
  passport: (evidenceId: string) =>
    request<Passport>(`/evidence/${encodeURIComponent(evidenceId)}/passport`),
  evidence: () => request<EvidenceListItem[]>("/evidence"),
  uploadDocument: (input: {
    file: File;
    caseId: string;
    title: string;
    documentType: string;
    classificationLevel: number;
    evidenceId?: string;
  }) => {
    const form = new FormData();
    form.set("file", input.file);
    form.set("case_id", input.caseId);
    form.set("title", input.title);
    form.set("document_type", input.documentType);
    form.set("classification_level", String(input.classificationLevel));
    if (input.evidenceId) form.set("evidence_id", input.evidenceId);
    return request<UploadResult>("/documents", { method: "POST", body: form });
  },
  createDocumentVersion: (
    documentId: string,
    file: File,
    changeReason: string,
  ) => {
    const form = new FormData();
    form.set("file", file);
    form.set("change_reason", changeReason);
    return request<UploadResult>(
      `/documents/${encodeURIComponent(documentId)}/versions`,
      { method: "POST", body: form },
    );
  },
  caseBrief: (caseNumber: string) =>
    request<AIBrief>(`/ai/case/${encodeURIComponent(caseNumber)}/brief`, {
      method: "POST",
    }),
  askCase: (caseNumber: string, question: string) =>
    request<AIBrief>(`/ai/case/${encodeURIComponent(caseNumber)}/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
  grants: (caseNumber?: string) =>
    request<AccessGrant[]>(
      `/access/grants${caseNumber ? `?case_number=${encodeURIComponent(caseNumber)}` : ""}`,
    ),
  createGrant: (input: {
    documentId: string;
    subjectEmail: string;
    permissions: string;
    expiresAt: string;
    reason: string;
  }) =>
    request<AccessGrant>("/access/grants", {
      method: "POST",
      body: JSON.stringify({
        document_id: input.documentId,
        subject_email: input.subjectEmail,
        permissions: input.permissions,
        expires_at: input.expiresAt,
        reason: input.reason,
      }),
    }),
  audit: (caseNumber?: string) =>
    request<AuditEvent[]>(
      `/audit${caseNumber ? `?case_number=${encodeURIComponent(caseNumber)}` : ""}`,
    ),
  integrations: () => request<IntegrationStatus[]>("/integrations"),
  checkpoint: () =>
    request<MerkleResult>("/blockchain/checkpoints", { method: "POST" }),
  merkleProof: (eventId: string) =>
    request<MerkleResult>(
      `/blockchain/merkle/${encodeURIComponent(eventId)}/proof`,
    ),
  verificationReport: (caseNumber: string) =>
    requestBlob(`/cases/${encodeURIComponent(caseNumber)}/verification-report`),
  verify: (file: File, documentVersionId: string) => {
    const form = new FormData();
    form.set("file", file);
    form.set("document_version_id", documentVersionId);
    return request<{
      status: string;
      expected?: string;
      actual?: string;
      documentVersionId?: string;
    }>("/verification/document", { method: "POST", body: form });
  },
};
