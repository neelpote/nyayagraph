"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Hash, Status } from "@/components/status";
import { api } from "@/lib/api";
import type { Passport } from "@/lib/types";

export default function EvidencePassport({ params }: { params: Promise<{ evidenceId: string }> }) {
  const { evidenceId } = use(params);
  const id = decodeURIComponent(evidenceId);
  const [data, setData] = useState<Passport | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.passport(id).then(setData).catch((reason: Error) => setError(reason.message)); }, [id]);
  return <AppShell><div className="page-content passport-page">
    {error && <div className="error-banner">Evidence passport unavailable: {error}. This record may be restricted or the API may be offline.</div>}
    {!data && !error && <div className="page-loading">Loading verified evidence record?</div>}
    {data && <><div className="breadcrumbs"><Link href={`/cases/${encodeURIComponent(data.caseId)}`}>{data.caseId}</Link><span>/</span> Evidence passport</div><section className="passport-hero"><div><div className="eyebrow">EVIDENCE PASSPORT</div><h1>{data.evidenceId}</h1><p>Registered evidence and associated provenance record.</p><Status tone={data.hashVerified && data.signatureVerified ? "good" : "danger"}>{data.hashVerified && data.signatureVerified ? "Provenance verified" : "Review required"}</Status></div><div className="passport-stamp"><span>AUTHENTICITY</span><b>{data.signatureVerified ? "?" : "!"}</b><strong>{data.signatureVerified ? "Signature verified" : "Signature unverified"}</strong></div></section><section className="passport-grid"><div className="panel passport-details"><h2>Fingerprint & version</h2><dl><dt>Original SHA-256</dt><dd><Hash value={data.sha256Original}/></dd><dt>Encrypted SHA-256</dt><dd><Hash value={data.sha256Encrypted}/></dd><dt>Version</dt><dd>V{data.version} ? immutable record</dd><dt>Classification</dt><dd><Status tone="neutral">{data.classification}</Status></dd><dt>Storage backend</dt><dd>{data.storageBackend || "Unavailable"}</dd></dl></div><div className="panel passport-details"><h2>Custody & source</h2><dl><dt>Creator organisation</dt><dd>{data.creatorOrganization || "Unavailable"}</dd><dt>Creator role</dt><dd>{data.creatorRole?.replaceAll("_", " ") || "Unavailable"}</dd><dt>Current custodian</dt><dd>{data.custodian}</dd><dt>Captured</dt><dd>{data.captureTimestamp ? new Date(data.captureTimestamp).toLocaleString() : "Unavailable"}</dd><dt>Custody status</dt><dd><Status tone={data.custodyStatus === "WARNING" ? "warning" : "good"}>{data.custodyStatus}</Status></dd></dl></div><div className="panel passport-details ledger-card"><h2>Independent verification</h2><dl><dt>Ledger transaction</dt><dd>{data.fabricTransaction ? <Hash value={data.fabricTransaction}/> : "Pending registration"}</dd><dt>Ledger mode</dt><dd>{data.ledgerMode || "Unavailable"}</dd><dt>Merkle batch</dt><dd>{data.merkleBatch ?? "Pending checkpoint"}</dd><dt>Anchor status</dt><dd><Status tone={data.publicAnchorVerified ? "good" : "warning"}>{data.anchorStatus || "Pending"}</Status></dd></dl><div className="ledger-steps compact"><span>HASH</span><i>?</i><span>LEDGER</span><i>?</i><span>ROOT</span></div></div><div className="panel custody-panel"><h2>Chain of custody</h2><div className="timeline">{data.custodyHistory.map(item => <div className="timeline-item" key={`${item.time}-${item.event}`}><span className="timeline-dot"/><div><div className="timeline-time">{new Date(item.time).toLocaleString()}</div><b>{item.event.replaceAll("_", " ")}</b><p>{item.purpose}</p></div></div>)}</div></div></section></>}
  </div></AppShell>;
}
