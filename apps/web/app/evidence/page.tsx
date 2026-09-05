"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Status } from "@/components/status";
import { api } from "@/lib/api";
import type { EvidenceListItem } from "@/lib/types";

export default function EvidenceRegister() {
  const [items, setItems] = useState<EvidenceListItem[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { api.evidence().then(setItems).catch((reason: Error) => setError(reason.message)); }, []);
  return <AppShell><div className="page-content"><div className="page-heading"><div><div className="eyebrow">AUTHORIZED INVENTORY</div><h1>Evidence register</h1><p>Evidence visible under the current case assignment, clearance and grant policy.</p></div><Status tone="neutral">{items.length} visible</Status></div>{error && <div className="error-banner">{error}</div>}<section className="panel"><div className="record-list">{items.map(item => <div className="record-row" key={item.id}><div className="record-icon">?</div><div><b>{item.code} ? {item.description}</b><small>{item.caseNumber} ? {item.type}</small></div><Status tone={item.status === "VERIFIED" ? "good" : "warning"}>{item.status}</Status><Link href={`/evidence/${item.code}`}>Passport ?</Link></div>)}</div></section></div></AppShell>;
}
