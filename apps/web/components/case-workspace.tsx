"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type {
  AuditEvent,
  CaseRecord,
  GraphData,
  Passport,
  TimelineEvent,
} from "@/lib/types";
import { Hash, Status } from "./status";

function Timeline({ events }: { events: TimelineEvent[] }) {
  return events.length ? (
    <div className="timeline">
      {events.map((item) => (
        <div className="timeline-item" key={`${item.time}-${item.title}`}>
          <span className="timeline-dot" />
          <div>
            <div className="timeline-time">
              {new Date(item.time).toLocaleString(undefined, {
                dateStyle: "medium",
                timeStyle: "short",
              })}{" "}
              {item.state && (
                <Status
                  tone={
                    item.state === "VERIFIED"
                      ? "good"
                      : item.state === "RESTRICTED"
                        ? "neutral"
                        : "warning"
                  }
                >
                  {item.state}
                </Status>
              )}
            </div>
            <b>{item.title}</b>
            <p>{item.description}</p>
          </div>
        </div>
      ))}
    </div>
  ) : (
    <Empty text="No authorized timeline events were returned." />
  );
}
function Graph({ data }: { data: GraphData | null }) {
  if (!data?.nodes.length)
    return <Empty text="No authorized relationships were returned." />;
  return (
    <>
      <div className="graph">
        <div className="graph-line one" />
        <div className="graph-line two" />
        {data.nodes.slice(0, 6).map((node, index) => (
          <div className={`graph-node node-${index}`} key={node.id}>
            <small>{node.type || "ENTITY"}</small>
            {node.label}
          </div>
        ))}
        <div className="graph-caption">
          Relationship graph · authorized records only
        </div>
      </div>
      <div className="edge-key">
        {data.edges.map((edge, index) => (
          <span key={`${edge.source}-${edge.target}-${index}`}>
            {edge.source} <b>{edge.label || "CONNECTED TO"}</b> {edge.target}
          </span>
        ))}
      </div>
    </>
  );
}
function Empty({ text }: { text: string }) {
  return <div className="inline-empty">{text}</div>;
}
function PanelTitle({
  title,
  sub,
  action,
}: {
  title: string;
  sub: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="panel-title">
      <div>
        <h2>{title}</h2>
        <p>{sub}</p>
      </div>
      {action}
    </div>
  );
}

export function CaseWorkspace({ caseNumber }: { caseNumber: string }) {
  const [record, setRecord] = useState<CaseRecord | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [passport, setPassport] = useState<Passport | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");
  const [secondaryErrors, setSecondaryErrors] = useState<string[]>([]);
  const [tab, setTab] = useState("Overview");
  useEffect(() => {
    let active = true;
    async function load() {
      const main = await Promise.allSettled([
        api.case(caseNumber),
        api.timeline(caseNumber),
        api.graph(caseNumber),
        api.caseBrief(caseNumber),
      ]);
      if (!active) return;
      if (main[0].status === "fulfilled") {
        const caseRecord = main[0].value;
        if (main[3].status === "fulfilled") caseRecord.aiBrief = main[3].value;
        setRecord(caseRecord);
      }
      else
        setError(
          main[0].reason instanceof Error
            ? main[0].reason.message
            : "Case access failed",
        );
      if (main[1].status === "fulfilled") setTimeline(main[1].value);
      if (main[2].status === "fulfilled") setGraph(main[2].value);
      setSecondaryErrors(
        main
          .slice(1)
          .filter((item) => item.status === "rejected")
          .map((item) =>
            item.status === "rejected" && item.reason instanceof Error
              ? item.reason.message
              : "Related service failed",
          ),
      );
    }
    load();
    return () => {
      active = false;
    };
  }, [caseNumber]);
  useEffect(() => {
    if (!record) return;
    const evidence = record.evidence?.[0];
    if (evidence)
      api
        .passport(evidence.code)
        .then(setPassport)
        .catch(() => undefined);
    api
      .audit(caseNumber)
      .then(setAudit)
      .catch(() => undefined);
  }, [record, caseNumber]);
  const tabs = [
    "Overview",
    "Timeline",
    "People",
    "Evidence",
    "Documents",
    "AI Insights",
    "Knowledge graph",
    "Custody",
    "Audit",
    "Verification",
  ];
  const integrity =
    typeof record?.integrity === "object" ? record.integrity : undefined;
  const integrityLabel = useMemo(
    () =>
      !record
        ? "Loading integrity checks"
        : integrity?.custody?.warnings ||
            integrity?.missingAttachments ||
            integrity?.timelineDiscrepancies
          ? "Verified with warnings"
          : "Verified",
    [record, integrity],
  );
  return (
    <div className="workspace">
      {error && (
        <div className="error-banner">
          Case data could not be loaded: {error}. Confirm the API is running and
          that your role has case access.
        </div>
      )}
      {secondaryErrors.length > 0 && (
        <div className="service-notice">
          <b>Some case services are unavailable</b>
          <p>
            {secondaryErrors.join(" · ")}. Available sections remain usable.
          </p>
        </div>
      )}
      <section className="case-hero">
        <div>
          <div className="eyebrow">
            CASE WORKSPACE / {record?.jurisdiction || "AUTHORIZED JURISDICTION"}
          </div>
          <h1>{caseNumber}</h1>
          <p>
            {record?.title ||
              (error ? "Case details unavailable" : "Loading verified case…")}
          </p>
          <div className="hero-meta">
            <Status tone="good">
              {record?.status?.replaceAll("_", " ") || "Loading status"}
            </Status>
            {record?.firNumber && <span>FIR {record.firNumber}</span>}
            <span>Records shown by current authorization</span>
          </div>
        </div>
        <div className="integrity-seal">
          <span>CASE INTEGRITY</span>
          <b>{record ? "✓" : "·"}</b>
          <strong>{integrityLabel}</strong>
          <small>Deterministic checks · no trust score</small>
        </div>
      </section>
      <div className="case-tabs">
        {tabs.map((item) => (
          <button
            key={item}
            className={tab === item ? "selected" : ""}
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}
      </div>
      <TabContent
        tab={tab}
        record={record}
        timeline={timeline}
        graph={graph}
        passport={passport}
        audit={audit}
        caseNumber={caseNumber}
      />
    </div>
  );
}

function TabContent({
  tab,
  record,
  timeline,
  graph,
  passport,
  audit,
  caseNumber,
}: {
  tab: string;
  record: CaseRecord | null;
  timeline: TimelineEvent[];
  graph: GraphData | null;
  passport: Passport | null;
  audit: AuditEvent[];
  caseNumber: string;
}) {
  if (tab === "Overview")
    return (
      <Overview record={record} timeline={timeline} caseNumber={caseNumber} />
    );
  if (tab === "Timeline")
    return (
      <section className="panel tab-panel">
        <PanelTitle
          title="Case timeline"
          sub="Evidence, source, and custody events in chronological order."
        />
        <Timeline events={timeline} />
      </section>
    );
  if (tab === "People") {
    const people =
      graph?.nodes.filter((node) =>
        ["PERSON", "WITNESS", "SUSPECT", "OFFICER"].includes(
          (node.type || "").toUpperCase(),
        ),
      ) || [];
    return (
      <section className="panel tab-panel">
        <PanelTitle
          title="People & participants"
          sub="Only identities present in your authorized graph are listed."
        />
        <div className="entity-grid">
          {people.map((person) => (
            <article key={person.id}>
              <span>{person.label.slice(0, 1)}</span>
              <div>
                <b>{person.label}</b>
                <small>{person.type}</small>
              </div>
            </article>
          ))}
        </div>
        {!people.length && (
          <Empty text="No authorized person entities were returned. Restricted identities remain hidden." />
        )}
      </section>
    );
  }
  if (tab === "Evidence")
    return (
      <section className="panel tab-panel">
        <PanelTitle
          title="Evidence register"
          sub={`${record?.evidence?.length || 0} items visible under your current clearance.`}
        />
        <div className="record-list">
          {record?.evidence?.map((item) => (
            <div className="record-row" key={item.id}>
              <div className="record-icon">◇</div>
              <div>
                <b>
                  {item.code} · {item.description}
                </b>
                <small>{item.type.replaceAll("_", " ")}</small>
              </div>
              <Status tone={item.status === "VERIFIED" ? "good" : "warning"}>
                {item.status}
              </Status>
              <Link href={`/evidence/${item.code}`}>Open passport →</Link>
            </div>
          ))}
        </div>
        {record && !record.evidence?.length && (
          <Empty text="No evidence is authorized for this role." />
        )}
      </section>
    );
  if (tab === "Documents")
    return (
      <section className="panel tab-panel">
        <PanelTitle
          title="Authorized documents"
          sub="Restricted documents are removed by the backend policy before this response."
          action={
            <Link className="primary-button" href="/documents">
              Register document
            </Link>
          }
        />
        <div className="record-list">
          {record?.documents?.map((doc) => (
            <div className="record-row" key={doc.id}>
              <div className="record-icon">▤</div>
              <div>
                <b>{doc.title}</b>
                <small>
                  {doc.type.replaceAll("_", " ")} · Classification L
                  {doc.classification}
                </small>
              </div>
              <span className="record-version">
                CURRENT
                <br />
                <b>V1</b>
              </span>
              <Link href={`/verification?version=${doc.versionId || ""}`}>
                Verify →
              </Link>
            </div>
          ))}
        </div>
        {record && !record.documents?.length && (
          <Empty text="No documents are authorized for this role." />
        )}
      </section>
    );
  if (tab === "AI Insights")
    return (
      <section className="panel tab-panel">
        <PanelTitle
          title="AI insights"
          sub={
            record?.aiBrief?.disclaimer ||
            "Evidence-grounded support only; never a guilt or legal determination."
          }
          action={
            <Link className="primary-button" href="/ai">
              Ask a question
            </Link>
          }
        />
        <p className="answer-overview">
          {record?.aiBrief?.caseOverview ||
            "No authorized AI overview was returned."}
        </p>
        <div className="claim-list">
          {record?.aiBrief?.claims?.map((claim, index) => (
            <article key={`${claim.claim}-${index}`}>
              <span className="claim-index">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <p>{claim.claim}</p>
                <div className="claim-meta">
                  <Status
                    tone={claim.status === "SUPPORTED" ? "good" : "warning"}
                  >
                    {claim.status}
                  </Status>
                  {claim.sources.map((source) => (
                    <Link
                      className="citation"
                      key={`${source.documentId}-${source.page}`}
                      href={`/documents?source=${encodeURIComponent(source.documentId)}`}
                    >
                      {source.documentTitle || source.documentId} · Page {source.page || "—"}
                    </Link>
                  ))}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>
    );
  if (tab === "Knowledge graph")
    return (
      <section className="panel tab-panel">
        <PanelTitle
          title="Knowledge graph"
          sub={`Provider: ${graph?.provider?.replaceAll("_", " ") || "Unavailable"}. Relationships are derived only from authorized records.`}
        />
        <Graph data={graph} />
      </section>
    );
  if (tab === "Custody")
    return (
      <section className="panel tab-panel">
        <PanelTitle
          title="Chain of custody"
          sub={
            passport
              ? `Evidence ${passport.evidenceId} · ${passport.ledgerMode?.replaceAll("_", " ")}`
              : "Loading the first authorized evidence passport."
          }
        />
        {passport ? (
          <>
            <div className="custody-summary">
              <Status
                tone={
                  passport.custodyStatus === "VERIFIED" ? "good" : "warning"
                }
              >
                {passport.custodyStatus}
              </Status>
              <span>
                Current custodian: <b>{passport.custodian}</b>
              </span>
              <span>
                Ledger: <b>{passport.fabricTransaction || "Pending"}</b>
              </span>
            </div>
            <Timeline
              events={passport.custodyHistory.map((item) => ({
                time: item.time,
                title: item.event.replaceAll("_", " "),
                description: item.purpose,
              }))}
            />
          </>
        ) : (
          <Empty text="No custody history is available for the visible evidence." />
        )}
      </section>
    );
  if (tab === "Audit")
    return (
      <section className="panel tab-panel">
        <PanelTitle
          title="Case audit"
          sub="Live activity records only; unavailable audit data is never synthesized."
          action={
            <Link className="text-button" href="/audit">
              Open audit explorer →
            </Link>
          }
        />
        {audit.length ? (
          <div className="mini-audit">
            {audit.slice(0, 8).map((event) => (
              <div key={event.id}>
                <time>{new Date(event.createdAt).toLocaleString()}</time>
                <b>{event.action.replaceAll("_", " ")}</b>
                <span>
                  {event.resourceType} {event.resourceId || ""}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <Empty text="The audit endpoint is unavailable or returned no case events." />
        )}
      </section>
    );
  return <VerificationTools caseNumber={caseNumber} />;
}

function VerificationTools({ caseNumber }: { caseNumber: string }) {
  const [eventId, setEventId] = useState("");
  const [proof, setProof] = useState<Awaited<
    ReturnType<typeof api.merkleProof>
  > | null>(null);
  const [error, setError] = useState("");
  const [reporting, setReporting] = useState(false);
  async function verifyProof() {
    setError("");
    setProof(null);
    try {
      setProof(await api.merkleProof(eventId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Proof lookup failed.");
    }
  }
  async function report() {
    setReporting(true);
    setError("");
    try {
      const blob = await api.verificationReport(caseNumber);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${caseNumber}-verification-report.html`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Report service unavailable.");
    } finally {
      setReporting(false);
    }
  }
  return (
    <section className="panel tab-panel">
      <PanelTitle
        title="Independent verification"
        sub="Verify a provenance event or generate the court-facing integrity package."
      />
      <div className="verification-actions">
        <div>
          <h3>Document fingerprint</h3>
          <p>Compare a local file to a registered immutable version.</p>
          <Link className="primary-button" href="/verification">
            Verify local file →
          </Link>
        </div>
        <div>
          <h3>Merkle proof</h3>
          <p>
            Enter an audit/provenance event identifier from a completed
            checkpoint.
          </p>
          <label>
            Event ID
            <input
              value={eventId}
              onChange={(e) => setEventId(e.target.value)}
              placeholder="Event UUID"
            />
          </label>
          <button
            className="primary-button"
            disabled={!eventId}
            onClick={verifyProof}
          >
            Verify proof →
          </button>
        </div>
        <div>
          <h3>Court verification report</h3>
          <p>
            Request hashes, signatures, custody, versions, proofs, and a
            privacy-safe QR result.
          </p>
          <button
            className="primary-button"
            onClick={report}
            disabled={reporting}
          >
            {reporting ? "Generating…" : "Generate report →"}
          </button>
        </div>
      </div>
      {error && (
        <div className="service-notice">
          <b>Verification action unavailable</b>
          <p>{error}. No success state was generated.</p>
        </div>
      )}
      {proof && (
        <div className="proof-result">
          <div className="ledger-steps">
            <span>EVENT</span>
            <i>→</i>
            <span>LEAF</span>
            <i>→</i>
            <span>PROOF</span>
            <i>→</i>
            <span>ROOT</span>
            <i>→</i>
            <span>ANCHOR</span>
          </div>
          <Status tone={proof.verified ? "good" : "danger"}>
            {proof.verified ? "Proof verified" : "Proof invalid"}
          </Status>
          <Hash value={proof.root || proof.merkleRoot} />
          <small>
            {proof.anchorStatus?.replaceAll("_", " ")} · Batch{" "}
            {proof.batchNumber || proof.batchId}
          </small>
        </div>
      )}
    </section>
  );
}

function Overview({
  record,
  timeline,
  caseNumber,
}: {
  record: CaseRecord | null;
  timeline: TimelineEvent[];
  caseNumber: string;
}) {
  const integrity =
    typeof record?.integrity === "object" ? record.integrity : undefined;
  return (
    <div className="overview-grid">
      <section className="panel briefing">
        <PanelTitle
          title="AI case brief"
          sub={
            record?.aiBrief?.disclaimer ||
            "Evidence-grounded investigative support only. Not a determination of guilt or legal conclusion."
          }
        />
        <p>
          {record?.aiBrief?.caseOverview ||
            "No authorized case brief was returned."}
        </p>
        <div className="source-row">
          {record?.aiBrief?.claims
            ?.flatMap((claim) => claim.sources)
            .map((source, index) => (
              <Link
                key={`${source.documentId}-${source.page}-${index}`}
                href={`/documents?source=${encodeURIComponent(source.documentId)}`}
              >
                {source.documentTitle || source.documentId} · Page {source.page || "—"}
              </Link>
            ))}
        </div>
        <Link className="text-button" href="/ai">
          Open AI assistant →
        </Link>
      </section>
      <section className="panel integrity-panel">
        <PanelTitle
          title="Integrity checks"
          sub="Deterministic verification, not an opaque trust score."
        />
        <ul className="checks">
          <li>
            <b>✓</b> {integrity?.documents?.verified ?? 0}/
            {integrity?.documents?.total ?? 0} document fingerprints verified
          </li>
          <li>
            <b>✓</b> {integrity?.signatures?.valid ?? 0}/
            {integrity?.signatures?.total ?? 0} signatures valid
          </li>
          <li className="warn">
            <b>!</b> {integrity?.custody?.warnings ?? 0} custody continuity
            warnings
          </li>
          <li className="warn">
            <b>!</b> {integrity?.missingAttachments ?? 0} referenced attachments
            missing
          </li>
        </ul>
      </section>
      <section className="panel alerts">
        <PanelTitle
          title="Review alerts"
          sub="Items requiring human assessment."
        />
        {record?.alerts?.map((alert) => (
          <div className="alert" key={alert.type}>
            <i>!</i>
            <div>
              <b>{alert.type.replaceAll("_", " ")}</b>
              <p>{alert.message}</p>
            </div>
          </div>
        ))}
        {record && !record.alerts?.length && (
          <Empty text="No review alerts returned." />
        )}
      </section>
      <section className="panel recent">
        <PanelTitle
          title="Recent timeline"
          sub="Latest authorized case activity."
        />
        <Timeline events={timeline.slice(0, 3)} />
      </section>
      <section className="panel key-evidence">
        <PanelTitle
          title="Key evidence"
          sub="Visible evidence and provenance at a glance."
        />
        {record?.evidence?.slice(0, 4).map((item) => (
          <div className="evidence-row" key={item.id}>
            <div>
              <small>
                {item.code} · {item.type}
              </small>
              <b>{item.description}</b>
              <span>{item.status}</span>
            </div>
            <Link href={`/evidence/${item.code}`}>Open passport →</Link>
          </div>
        ))}
      </section>
      <section className="panel ledger">
        <PanelTitle title="Provenance ledger" sub="Shared provenance status." />
        <div className="ledger-steps">
          <span>HASH</span>
          <i>→</i>
          <span>LEDGER</span>
          <i>→</i>
          <span>MERKLE</span>
          <i>→</i>
          <span>ANCHOR</span>
        </div>
        <Status tone={integrity?.publicAnchorVerified ? "good" : "warning"}>
          {integrity?.publicAnchorVerified
            ? "External anchor verified"
            : "External checkpoint pending"}
        </Status>
        <p>
          Ledger mode:{" "}
          {integrity?.ledgerMode?.replaceAll("_", " ") || "Unavailable"}.
          Confidential evidence is never placed on a public chain.
        </p>
        <Link className="text-button" href={`/cases/${caseNumber}`}>
          Case verification controls are available in the Verification tab.
        </Link>
      </section>
    </div>
  );
}
