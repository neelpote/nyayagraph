"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Status } from "@/components/status";
import { api } from "@/lib/api";
import type { Passport } from "@/lib/types";

export default function Custody() {
  const [passport, setPassport] = useState<Passport | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.evidence()
      .then((items) => {
        if (!items[0]) throw new Error("No authorized evidence is available");
        return api.passport(items[0].id);
      })
      .then(setPassport)
      .catch((reason: Error) => setError(reason.message));
  }, []);
  return <AppShell><div className="page-content"><div className="page-heading"><div><div className="eyebrow">CHAIN OF CUSTODY</div><h1>Custody continuity</h1><p>Signed transfers and detected continuity warnings from the authorized evidence record.</p></div>{passport && <Status tone={passport.custodyStatus === "WARNING" ? "warning" : "good"}>{passport.custodyStatus}</Status>}</div>{error && <div className="error-banner">{error}</div>}<section className="panel tab-panel">{passport ? <><div className="custody-summary"><span>Evidence: <b>{passport.evidenceId}</b></span><span>Current custodian: <b>{passport.custodian}</b></span><span>Ledger: <b>{passport.fabricTransaction || "Pending"}</b></span></div><div className="timeline">{passport.custodyHistory.map(item => <div className="timeline-item" key={`${item.time}-${item.hash}`}><span className="timeline-dot"/><div><div className="timeline-time">{new Date(item.time).toLocaleString()}</div><b>{item.event.replaceAll("_", " ")}</b><p>{item.purpose}</p><small>{item.hash}</small></div></div>)}</div></> : !error && <div className="inline-empty">Loading authorized custody records…</div>}</section></div></AppShell>;
}
