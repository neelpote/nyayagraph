"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Status } from "@/components/status";
import { useAuthorizedCase } from "@/hooks/use-authorized-case";
import { api } from "@/lib/api";
import type { AccessGrant, IntegrityResult } from "@/lib/types";

export default function Dashboard() {
  const { cases, record, loading, error } = useAuthorizedCase();
  const [grants, setGrants] = useState<AccessGrant[]>([]);
  useEffect(() => {
    if (record)
      api
        .grants(record.caseNumber)
        .then(setGrants)
        .catch(() => setGrants([]));
  }, [record]);
  const alerts = record?.alerts || [];
  const integrity =
    typeof record?.integrity === "object"
      ? (record.integrity as IntegrityResult)
      : undefined;
  const activeGrants = grants.filter(
    (grant) =>
      grant.status === "ACTIVE" && new Date(grant.expiresAt) > new Date(),
  ).length;
  const ledgerMode = integrity?.ledgerMode || "PENDING";
  return (
    <AppShell>
      <div className="page-content">
        <div className="page-heading">
          <div>
            <div className="eyebrow">COMMAND DESK</div>
            <h1>Authorized casework</h1>
            <p>Review active cases and integrity alerts returned by the API.</p>
          </div>
          <Link className="primary-button" href="/cases">
            Find a case →
          </Link>
        </div>
        {error && (
          <div className="error-banner">
            Dashboard data unavailable: {error}
          </div>
        )}
        <section className="command-strip">
          <div>
            <small>ACTIVE CASES</small>
            <b>{loading ? "—" : cases.length}</b>
          </div>
          <div>
            <small>INTEGRITY WARNINGS</small>
            <b className="amber">{record ? alerts.length : "—"}</b>
          </div>
          <div>
            <small>TIME-LIMITED ACCESS</small>
            <b>{record ? activeGrants : "—"}</b>
          </div>
          <div>
            <small>LEDGER MODE</small>
            <Status tone={ledgerMode === "FABRIC" ? "good" : "warning"}>
              {ledgerMode.replaceAll("_", " ")}
            </Status>
          </div>
        </section>
        {record ? (
          <section className="dashboard-feature">
            <div className="featured-case">
              <div className="eyebrow">MOST RECENT AUTHORIZED CASE</div>
              <h2>{record.caseNumber}</h2>
              <p>{record.title}</p>
              <div className="featured-stat">
                <span>
                  <b>{record.evidence?.length ?? 0}</b> Evidence items
                </span>
                <span>
                  <b>{record.documents?.length ?? 0}</b> Documents
                </span>
                <span>
                  <b className="amber">{alerts.length}</b> Alerts
                </span>
              </div>
              <Link
                href={`/cases/${encodeURIComponent(record.caseNumber)}`}
                className="primary-button"
              >
                Open verified case →
              </Link>
            </div>
            <div className="dashboard-alerts">
              <h3>Requires attention</h3>
              {alerts.map((alert) => (
                <div key={`${alert.type}-${alert.message}`}>
                  <b>{alert.type.replaceAll("_", " ")}</b>
                  <p>{alert.message}</p>
                </div>
              ))}
              {!alerts.length && <p>No authorized alerts require review.</p>}
            </div>
          </section>
        ) : (
          !loading &&
          !error && (
            <div className="empty-state">
              <h1>No assigned cases</h1>
              <p>Your identity has no active case assignments.</p>
            </div>
          )
        )}
      </div>
    </AppShell>
  );
}
