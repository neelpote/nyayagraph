"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Status } from "@/components/status";
import { api } from "@/lib/api";
import type { AccessGrant } from "@/lib/types";
import { useAuthorizedCase } from "@/hooks/use-authorized-case";

export default function Access() {
  const { record, error: caseError } = useAuthorizedCase();
  const [grants, setGrants] = useState<AccessGrant[]>([]);
  const [resourceId, setResourceId] = useState("");
  const [subject, setSubject] = useState("");
  const [reason, setReason] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!record) return;
    api
      .grants(record.caseNumber)
      .then(setGrants)
      .catch((e: Error) =>
        setError(
          `${e.message}. Grant service is not active; no fabricated grants are shown.`,
        ),
      );
  }, [record]);
  async function create(event: FormEvent) {
    event.preventDefault();
    if (!record?.id) {
      setError("The case could not be resolved.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const grant = await api.createGrant({
        documentId: resourceId,
        subjectEmail: subject,
        permissions: "READ",
        expiresAt: new Date(expiresAt).toISOString(),
        reason,
      });
      setGrants((current) => [grant, ...current]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Grant request failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <AppShell>
      <div className="page-content">
        <div className="page-heading">
          <div>
            <div className="eyebrow">TIME-BOUND AUTHORIZATION</div>
            <h1>Temporary access</h1>
            <p>
              Grant the minimum document scope needed. Every decision must be
              audited and may be registered to the provenance ledger.
            </p>
          </div>
          <Status tone="warning">Supervisor review</Status>
        </div>
        <div className="access-layout">
          <form className="panel access-form" onSubmit={create}>
            <h2>Create restricted grant</h2>
            <p>
              Use backend identifiers from the case record. Expired grants stop
              retrieval and must never enter AI context.
            </p>
            <label>
              Resource document
              <select
                value={resourceId}
                onChange={(e) => setResourceId(e.target.value)}
                required
              >
                <option value="">Select authorized document</option>
                {record?.documents?.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.title} · L{doc.classification}
                  </option>
                ))}
              </select>
            </label>
            <label>
              External expert email
              <input
                type="email"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="expert@nyaya.local"
                required
              />
            </label>
            <label>
              Expires at
              <input
                type="datetime-local"
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
                required
              />
            </label>
            <label>
              Justification
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Why access is necessary and limited…"
                required
              />
            </label>
            {(error || caseError) && <div className="form-error">{error || caseError}</div>}
            <button className="primary-button full" disabled={busy}>
              {busy ? "Evaluating policy…" : "Grant temporary read access →"}
            </button>
          </form>
          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>Active grants</h2>
                <p>Current live API results</p>
              </div>
              <Status tone="neutral">{grants.length} records</Status>
            </div>
            <div className="grant-list">
              {grants.map((grant) => (
                <article key={grant.id}>
                  <div>
                    <b>
                      {grant.resourceType} · {grant.resourceId}
                    </b>
                    <small>
                      {grant.permissions} · expires{" "}
                      {new Date(grant.expiresAt).toLocaleString()}
                    </small>
                  </div>
                  <Status tone={grant.status === "ACTIVE" ? "good" : "warning"}>
                    {grant.status}
                  </Status>
                  <p>{grant.reason}</p>
                </article>
              ))}
              {!grants.length && (
                <div className="inline-empty">
                  No live access grants were returned.
                </div>
              )}
            </div>
            <div className="policy-note">
              <b>Authorization order</b>
              <span>
                Identity → assignment → clearance → resource relevance → active
                expiry → retrieval
              </span>
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
