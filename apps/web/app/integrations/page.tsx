"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Status } from "@/components/status";
import { api } from "@/lib/api";
import type { IntegrationStatus } from "@/lib/types";

const adapters: IntegrationStatus[] = [
  { id: "cctns", name: "CCTNS", status: "SIMULATED", authenticationMode: "Demo adapter", simulated: true }, { id: "esakshya", name: "eSakshya", status: "SIMULATED", authenticationMode: "Demo adapter", simulated: true }, { id: "icjs", name: "ICJS", status: "SIMULATED", authenticationMode: "Demo adapter", simulated: true }, { id: "ecourts", name: "eCourts", status: "SIMULATED", authenticationMode: "Demo adapter", simulated: true }, { id: "eforensics", name: "eForensics", status: "SIMULATED", authenticationMode: "Demo adapter", simulated: true }, { id: "eprosecution", name: "eProsecution", status: "SIMULATED", authenticationMode: "Demo adapter", simulated: true }
];
export default function Integrations() {
  const [live, setLive] = useState<IntegrationStatus[] | null>(null); const [error, setError] = useState("");
  useEffect(() => { api.integrations().then(setLive).catch((e: Error) => setError(e.message)); }, []); const rows = live || adapters;
  return <AppShell><div className="page-content"><div className="page-heading"><div><div className="eyebrow">JUSTICE SYSTEM ADAPTERS</div><h1>Integration boundary</h1><p>NyayaGraph sits above source systems. This MVP does not claim a live connection to any government service.</p></div><Status tone="warning">Simulation environment</Status></div>{error && <div className="simulation-banner"><b>SIMULATED ADAPTERS</b><span>The integration API is unavailable ({error}). Cards below describe interface placeholders only; no sync has occurred.</span></div>}<div className="integration-grid">{rows.map(adapter => <article className="integration-card" key={adapter.id}><div className="adapter-head"><span>{adapter.name.slice(0, 2).toUpperCase()}</span><div><h2>{adapter.name}</h2><small>JUSTICE SYSTEM ADAPTER</small></div></div><Status tone={adapter.simulated || adapter.status === "SIMULATED" ? "warning" : "good"}>{adapter.simulated || adapter.status === "SIMULATED" ? "SIMULATED ? NOT CONNECTED" : adapter.status}</Status><dl><dt>Last sync</dt><dd>{adapter.lastSync ? new Date(adapter.lastSync).toLocaleString() : "Never"}</dd><dt>Records imported</dt><dd>{adapter.recordsImported ?? 0}</dd><dt>Authentication</dt><dd>{adapter.authenticationMode || "Not configured"}</dd></dl><button disabled>{adapter.simulated || adapter.status === "SIMULATED" ? "Demo adapter only" : "View connection"}</button></article>)}</div></div></AppShell>;
}
