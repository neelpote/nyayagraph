"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Hash, Status } from "@/components/status";
import { api } from "@/lib/api";
import type { UploadResult } from "@/lib/types";
import { useAuthorizedCase } from "@/hooks/use-authorized-case";

export default function Documents() {
  const { record, error: loadError } = useAuthorizedCase();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [documentType, setDocumentType] = useState("OTHER");
  const [classification, setClassification] = useState(2);
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [versionFile, setVersionFile] = useState<File | null>(null);
  const [reason, setReason] = useState("");
  const [version, setVersion] = useState<UploadResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submitUpload(event: FormEvent) {
    event.preventDefault();
    if (!file || !record?.id) {
      setError("The case record and a supported file are required.");
      return;
    }
    setBusy(true);
    setError("");
    setVersion(null);
    try {
      setUpload(
        await api.uploadDocument({
          file,
          caseId: record.id,
          title: title || file.name,
          documentType,
          classificationLevel: classification,
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }
  async function submitVersion(event: FormEvent) {
    event.preventDefault();
    if (!upload || !versionFile || !reason.trim()) return;
    setBusy(true);
    setError("");
    try {
      setVersion(
        await api.createDocumentVersion(upload.documentId, versionFile, reason),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Version creation failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <AppShell>
      <div className="page-content">
        <div className="page-heading">
          <div>
            <div className="eyebrow">PRIVATE DOCUMENT VAULT</div>
            <h1>Documents & immutable versions</h1>
            <p>
              Files are authorized, fingerprinted, encrypted, and stored without
              overwriting earlier versions.
            </p>
          </div>
          {record && <Link className="text-button" href={`/cases/${encodeURIComponent(record.caseNumber)}`}>
            Open case workspace ?
          </Link>}
        </div>
        {loadError && (
          <div className="error-banner">
            Case documents unavailable: {loadError}. Sign in with a role
            assigned to this case.
          </div>
        )}
        <div className="document-layout">
          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>Authorized documents</h2>
                <p>
                  {record
                    ? `${record.documents?.length || 0} records visible to your current role`
                    : "Loading access-filtered records?"}
                </p>
              </div>
              <Status tone="neutral">ABAC filtered</Status>
            </div>
            <div className="record-list">
              {record?.documents?.map((doc) => (
                <div className="record-row" key={doc.id}>
                  <div className="record-icon">?</div>
                  <div>
                    <b>{doc.title}</b>
                    <small>
                      {doc.type.replaceAll("_", " ")} ? Classification L
                      {doc.classification}
                    </small>
                  </div>
                  <div className="record-version">
                    CURRENT
                    <br />
                    <b>V1</b>
                  </div>
                  <Link href={`/verification?version=${doc.versionId || ""}`}>
                    Verify ?
                  </Link>
                </div>
              ))}
              {record && !record.documents?.length && (
                <div className="inline-empty">
                  No documents are authorized for this role. Restricted records
                  are intentionally omitted.
                </div>
              )}
            </div>
          </section>
          <form className="panel upload-panel" onSubmit={submitUpload}>
            <div className="section-heading">
              <div>
                <h2>Register document</h2>
                <p>PDF, TXT, JPG, or PNG ? limits enforced by the API</p>
              </div>
              <span className="step-mark">01</span>
            </div>
            <label>
              Case
              <input value={record?.caseNumber || "No assigned case"} disabled />
            </label>
            <label>
              Title
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Defaults to filename"
              />
            </label>
            <div className="form-pair">
              <label>
                Document type
                <select
                  value={documentType}
                  onChange={(e) => setDocumentType(e.target.value)}
                >
                  <option>OTHER</option>
                  <option>FIR</option>
                  <option>WITNESS_STATEMENT</option>
                  <option>FORENSIC_REPORT</option>
                  <option>COURT_ORDER</option>
                </select>
              </label>
              <label>
                Classification
                <select
                  value={classification}
                  onChange={(e) => setClassification(Number(e.target.value))}
                >
                  <option value={1}>L1 ? Internal</option>
                  <option value={2}>L2 ? Confidential</option>
                  <option value={3}>L3 ? Restricted</option>
                </select>
              </label>
            </div>
            <label className="file-field">
              Original file
              <input
                type="file"
                accept=".pdf,.txt,.jpg,.jpeg,.png"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              <span>
                {file
                  ? `${file.name} ? ${(file.size / 1024).toFixed(1)} KB`
                  : "Choose evidence document"}
              </span>
            </label>
            {error && <div className="form-error">{error}</div>}
            <button
              className="primary-button full"
              disabled={busy || !record?.id}
            >
              {busy ? "Securing document?" : "Encrypt and register ?"}
            </button>
          </form>
        </div>
        {upload && (
          <section className="panel version-result">
            <div className="section-heading">
              <div>
                <div className="eyebrow">REGISTERED</div>
                <h2>Immutable version chain</h2>
              </div>
              <Status tone="good">Provenance verified</Status>
            </div>
            <div className="version-chain">
              <VersionNode label="V1" result={upload} />
              {version && (
                <>
                  <i>?</i>
                  <VersionNode
                    label={`V${version.versionNumber || 2}`}
                    result={version}
                  />
                </>
              )}
            </div>
            {!version && (
              <form className="new-version" onSubmit={submitVersion}>
                <div>
                  <b>Create the next version</b>
                  <p>
                    The registered V1 remains intact and the new version links
                    back to its fingerprint.
                  </p>
                </div>
                <label>
                  Change reason
                  <input
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Correction requested by?"
                    required
                  />
                </label>
                <label className="file-field">
                  Replacement file
                  <input
                    type="file"
                    accept=".pdf,.txt,.jpg,.jpeg,.png"
                    onChange={(e) =>
                      setVersionFile(e.target.files?.[0] || null)
                    }
                    required
                  />
                  <span>{versionFile?.name || "Choose the V2 file"}</span>
                </label>
                <button className="primary-button" disabled={busy}>
                  Create V2 ?
                </button>
              </form>
            )}
          </section>
        )}
      </div>
    </AppShell>
  );
}

function VersionNode({
  label,
  result,
}: {
  label: string;
  result: UploadResult;
}) {
  return (
    <div className="version-node">
      <span>{label}</span>
      <b>{result.documentVersionId}</b>
      <small>ORIGINAL SHA-256</small>
      <Hash value={result.sha256Original} />
      {result.previousVersionHash && (
        <>
          <small>PREVIOUS VERSION</small>
          <Hash value={result.previousVersionHash} />
        </>
      )}
      <em>{result.provenance.mode.replaceAll("_", " ")}</em>
    </div>
  );
}
