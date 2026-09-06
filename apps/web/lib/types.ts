export type Role =
  | "INVESTIGATING_OFFICER"
  | "FSL_OFFICER"
  | "EXTERNAL_EXPERT"
  | "AUDITOR"
  | "SUPERVISOR"
  | "PROSECUTOR"
  | "COURT_USER"
  | "ADMIN";

export interface Session {
  accessToken: string;
  user: {
    id: string;
    name: string;
    email: string;
    role: Role;
    clearanceLevel: number;
  };
}
export interface SourceCitation {
  documentId: string;
  documentVersionId?: string;
  documentTitle?: string;
  page?: number;
  chunkId?: string;
  sourceHash?: string;
}
export type ClaimStatus =
  | "SUPPORTED"
  | "PARTIALLY_SUPPORTED"
  | "CONFLICTING"
  | "UNSUPPORTED"
  | "INSUFFICIENT_EVIDENCE";

export type TrustLabel =
  | "Strongly Supported"
  | "Partially Supported"
  | "Conflicting Evidence"
  | "Unsupported"
  | "Insufficient Evidence";

export function trustLabel(status: string | undefined): TrustLabel {
  switch (status) {
    case "SUPPORTED": return "Strongly Supported";
    case "PARTIALLY_SUPPORTED": return "Partially Supported";
    case "CONFLICTING": return "Conflicting Evidence";
    case "UNSUPPORTED": return "Unsupported";
    default: return "Insufficient Evidence";
  }
}

export function trustTone(status: string | undefined): "good" | "warning" | "neutral" | "danger" {
  switch (status) {
    case "SUPPORTED": return "good";
    case "PARTIALLY_SUPPORTED": return "warning";
    case "CONFLICTING": return "warning";
    case "UNSUPPORTED": return "danger";
    default: return "neutral";
  }
}

export interface AIClaim {
  claim: string;
  confidence?: number;
  status: ClaimStatus | string;
  sources: SourceCitation[];
}

export interface AIBrief {
  answer?: string;
  mode?: string;
  disclaimer?: string;
  caseOverview?: string;
  claims?: AIClaim[];
  contradictions?: Array<{
    type?: string;
    description?: string;
    sources?: SourceCitation[];
  }>;
  missingInformation?: string[];
  /** Top-level trust status for the whole response. */
  status?: ClaimStatus | string;
  /** Alias used by the new case_agent (same value as status). */
  trustStatus?: ClaimStatus | string;
  /** DETERMINISTIC_DEMO or GROUNDED_LLM */
  generationMode?: string;
}
export interface IntegrityResult {
  documents?: { verified: number; total: number };
  custody?: { status: string; warnings: number };
  signatures?: { valid: number; total: number };
  missingAttachments?: number;
  timelineDiscrepancies?: number;
  expiredAccessGrants?: number;
  publicAnchorVerified?: boolean;
  ledgerMode?: string;
  custodyEvents?: number;
}
export interface CaseDocument {
  id: string;
  title: string;
  type: string;
  classification: number;
  versionId?: string;
}
export interface CaseEvidence {
  id: string;
  code: string;
  type: string;
  description: string;
  status: string;
}
export interface EvidenceListItem extends CaseEvidence {
  caseNumber: string;
  captureTime?: string;
}
export interface CaseRecord {
  id?: string;
  caseNumber: string;
  title: string;
  description?: string;
  caseType?: string;
  type?: string;
  status: string;
  jurisdiction?: string;
  firNumber?: string;
  policeStation?: string;
  incidentTime?: string;
  incidentLocation?: string;
  nextHearingAt?: string;
  updatedAt?: string;
  integrity?: string | IntegrityResult;
  evidence?: CaseEvidence[];
  documents?: CaseDocument[];
  alerts?: Array<{ type: string; message: string }>;
  aiBrief?: AIBrief;
}
export interface TimelineEvent {
  time: string;
  title: string;
  description?: string;
  state?: string;
}
export interface GraphData {
  provider?: string;
  nodes: Array<{ id: string; label: string; type?: string }>;
  edges: Array<{ id?: string; source: string; target: string; label?: string }>;
}
export interface CustodyRecord {
  event: string;
  time: string;
  purpose: string;
  hash: string;
}
export interface Passport {
  evidenceId: string;
  caseId: string;
  sha256Original: string;
  sha256Encrypted: string;
  creatorOrganization?: string | null;
  creatorRole?: string | null;
  captureTimestamp?: string;
  ingestionTimestamp?: string;
  version: number;
  custodian: string;
  classification: string;
  signatureVerified: boolean;
  hashVerified: boolean;
  custodyStatus: string;
  fabricTransaction?: string | null;
  merkleBatch?: number | null;
  publicTransaction?: string | null;
  publicAnchorVerified: boolean;
  anchorStatus?: string;
  ledgerMode?: string;
  storageBackend?: string;
  custodyHistory: CustodyRecord[];
}
export interface UploadResult {
  documentId: string;
  documentVersionId: string;
  versionNumber?: number;
  sha256Original: string;
  sha256Encrypted: string;
  previousVersionHash?: string | null;
  storagePolicy?: string;
  storageBackend?: string;
  provenance: { mode: string; transaction?: string };
}
export interface MerkleResult {
  batchId: string;
  batchNumber?: number;
  merkleRoot: string;
  eventCount?: number;
  anchorStatus?: string;
  publicTransaction?: string;
  chainId?: string;
  leaf?: string;
  root?: string;
  siblings?: Array<{ hash: string; position: "LEFT" | "RIGHT" }>;
  leafIndex?: number;
  verified?: boolean;
}
export interface AccessGrant {
  id: string;
  caseId?: string;
  resourceType: string;
  resourceId: string;
  subjectUserId?: string;
  subjectOrgId?: string;
  permissions: string;
  expiresAt: string;
  reason: string;
  status: string;
}
export interface AuditEvent {
  id: string;
  createdAt: string;
  action: string;
  resourceType: string;
  resourceId?: string;
  actorName?: string;
  authorizationDecision?: string;
  fabricTxId?: string;
}
export interface IntegrationStatus {
  id: string;
  name: string;
  status: string;
  lastSync?: string;
  recordsImported?: number;
  authenticationMode?: string;
  simulated?: boolean;
}
