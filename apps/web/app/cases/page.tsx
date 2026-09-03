"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Status } from "@/components/status";
import { api } from "@/lib/api";
import type { CaseRecord } from "@/lib/types";

export default function CasesPage() {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({
    caseNumber: "",
    title: "",
    firNumber: "",
    description: "",
    caseType: "Vehicle Theft",
    jurisdiction: "Pune, Maharashtra",
    policeStation: "Hadapsar Police Station",
  });
  useEffect(() => {
    api
      .cases()
      .then(setCases)
      .catch((e: Error) => setError(e.message));
  }, []);
  const list = cases.filter((c) =>
    `${c.caseNumber} ${c.title}`.toLowerCase().includes(query.toLowerCase()),
  );
  async function createCase(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    setError("");
    try {
      const result = await api.createCase({ ...draft, classificationLevel: 2 });
      setCases((current) => [
        {
          caseNumber: result.caseNumber,
          title: draft.title,
          caseType: draft.caseType,
          status: result.status,
        },
        ...current,
      ]);
      setDraft((current) => ({
        ...current,
        caseNumber: "",
        title: "",
        firNumber: "",
        description: "",
      }));
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Case creation failed",
      );
    } finally {
      setCreating(false);
    }
  }
  return (
    <AppShell>
      <div className="page-content">
        <div className="page-heading">
          <div>
            <div className="eyebrow">CASE REGISTRY</div>
            <h1>Authorized cases</h1>
            <p>Search by case identifier, title or jurisdiction.</p>
          </div>
        </div>
        <details className="panel upload-panel">
          <summary className="text-button">Create case</summary>
          <form onSubmit={createCase}>
            <div className="form-pair">
              <label>
                Case number
                <input
                  value={draft.caseNumber}
                  onChange={(event) =>
                    setDraft({ ...draft, caseNumber: event.target.value })
                  }
                  required
                />
              </label>
              <label>
                FIR number
                <input
                  value={draft.firNumber}
                  onChange={(event) =>
                    setDraft({ ...draft, firNumber: event.target.value })
                  }
                  required
                />
              </label>
            </div>
            <label>
              Title
              <input
                value={draft.title}
                onChange={(event) =>
                  setDraft({ ...draft, title: event.target.value })
                }
                required
              />
            </label>
            <label>
              Description
              <textarea
                value={draft.description}
                onChange={(event) =>
                  setDraft({ ...draft, description: event.target.value })
                }
                required
              />
            </label>
            <div className="form-pair">
              <label>
                Type
                <input
                  value={draft.caseType}
                  onChange={(event) =>
                    setDraft({ ...draft, caseType: event.target.value })
                  }
                  required
                />
              </label>
              <label>
                Jurisdiction
                <input
                  value={draft.jurisdiction}
                  onChange={(event) =>
                    setDraft({ ...draft, jurisdiction: event.target.value })
                  }
                  required
                />
              </label>
            </div>
            <label>
              Police station
              <input
                value={draft.policeStation}
                onChange={(event) =>
                  setDraft({ ...draft, policeStation: event.target.value })
                }
                required
              />
            </label>
            <button className="primary-button" disabled={creating}>
              {creating ? "Registering…" : "Register case →"}
            </button>
          </form>
        </details>
        {error && (
          <div className="error-banner">
            Live registry unavailable: {error}. No fallback records are
            displayed.
          </div>
        )}
        <div className="table-tools">
          <input
            aria-label="Search cases"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search case ID or keywords…"
          />
          <span>
            {list.length} case{list.length === 1 ? "" : "s"}
          </span>
        </div>
        <section className="table-panel">
          <table>
            <thead>
              <tr>
                <th>Case ID</th>
                <th>Case</th>
                <th>Status</th>
                <th>Integrity</th>
                <th>Updated</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.map((c) => (
                <tr key={c.caseNumber}>
                  <td>
                    <b>{c.caseNumber}</b>
                    <small>{c.caseType || "Criminal investigation"}</small>
                  </td>
                  <td>
                    {c.title}
                    <small>{c.type || c.caseType || "Case record"}</small>
                  </td>
                  <td>
                    <Status tone="good">{c.status.replaceAll("_", " ")}</Status>
                  </td>
                  <td>
                    <Status
                      tone={
                        typeof c.integrity === "object" &&
                        (c.integrity.custody?.warnings ||
                          c.integrity.missingAttachments ||
                          c.integrity.timelineDiscrepancies)
                          ? "warning"
                          : "good"
                      }
                    >
                      {typeof c.integrity === "object" &&
                      (c.integrity.custody?.warnings ||
                        c.integrity.missingAttachments ||
                        c.integrity.timelineDiscrepancies)
                        ? "Warnings"
                        : "Verified"}
                    </Status>
                  </td>
                  <td>
                    {c.updatedAt
                      ? new Date(c.updatedAt).toLocaleDateString()
                      : "—"}
                  </td>
                  <td>
                    <Link
                      className="text-button"
                      href={`/cases/${c.caseNumber}`}
                    >
                      Open →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </AppShell>
  );
}
