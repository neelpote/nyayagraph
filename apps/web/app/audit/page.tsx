"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Status } from "@/components/status";
import { api } from "@/lib/api";
import type { AuditEvent } from "@/lib/types";
import { useAuthorizedCase } from "@/hooks/use-authorized-case";

export default function Audit() {
  const { record, error: caseError } = useAuthorizedCase();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  useEffect(() => {
    if (!record) return;
    api
      .audit(record.caseNumber)
      .then(setEvents)
      .catch((e: Error) => setError(e.message));
  }, [record]);
  const visible = events.filter((event) =>
    `${event.action} ${event.resourceType} ${event.resourceId || ""}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <AppShell>
      <div className="page-content">
        <div className="page-heading">
          <div>
            <div className="eyebrow">IMMUTABLE ACTIVITY RECORD</div>
            <h1>Audit logs</h1>
            <p>
              Access, verification, AI, custody, and export actions for
              authorized review.
            </p>
          </div>
          {record && <Status tone="neutral">Case {record.caseNumber}</Status>}
        </div>
        {(error || caseError) && (
          <div className="service-notice">
            <b>Audit service unavailable</b>
            <p>{error || caseError}. No placeholder events are displayed.</p>
          </div>
        )}
        <div className="table-tools">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by action or resource…"
          />
          <span>{visible.length} live events</span>
        </div>
        <div className="table-panel">
          <table>
            <thead>
              <tr>
                <th>TIME</th>
                <th>ACTION</th>
                <th>RESOURCE</th>
                <th>ACTOR</th>
                <th>DECISION</th>
                <th>LEDGER</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((event) => (
                <tr key={event.id}>
                  <td>{new Date(event.createdAt).toLocaleString()}</td>
                  <td>
                    <b>{event.action.replaceAll("_", " ")}</b>
                  </td>
                  <td>
                    {event.resourceType}
                    <small>{event.resourceId || "—"}</small>
                  </td>
                  <td>{event.actorName || "Authenticated user"}</td>
                  <td>
                    <Status
                      tone={
                        event.authorizationDecision === "DENIED"
                          ? "danger"
                          : "good"
                      }
                    >
                      {event.authorizationDecision || "RECORDED"}
                    </Status>
                  </td>
                  <td>{event.fabricTxId ? "Registered" : "Operational log"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!error && !visible.length && (
            <div className="table-empty">
              No audit events matched this view.
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
