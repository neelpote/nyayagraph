"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Status } from "@/components/status";
import { api } from "@/lib/api";
import type { AIBrief } from "@/lib/types";
import { useAuthorizedCase } from "@/hooks/use-authorized-case";

const prompts = [
  "Summarize this case.",
  "Show all timing contradictions.",
  "What forensic findings are available?",
];

export default function AI() {
  const { record, loading: caseLoading, error: caseError } = useAuthorizedCase();
  const [brief, setBrief] = useState<AIBrief | null>(null);
  const [question, setQuestion] = useState(prompts[0]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState<"brief" | "question">("brief");
  const [loadingBrief, setLoadingBrief] = useState(true);
  const caseNumber = record?.caseNumber;
  useEffect(() => {
    if (!caseNumber) return;
    let active = true;
    api.caseBrief(caseNumber)
      .then((response) => {
        if (active) {
          setBrief(response);
          setSource("brief");
        }
      })
      .catch((reason: Error) => {
        if (active) setError(reason.message);
      })
      .finally(() => {
        if (active) setLoadingBrief(false);
      });
    return () => { active = false; };
  }, [caseNumber]);
  const activeBrief = brief;
  async function ask(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (!record) throw new Error("No authorized case is selected");
      setBrief(await api.askCase(record.caseNumber, question));
      setSource("question");
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI request failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <AppShell>
      <div className="page-content ai-page">
        <div className="page-heading">
          <div>
            <div className="eyebrow">SECURE CASE ASSISTANT</div>
            <h1>Ask authorized evidence</h1>
            <p>
              Evidence-grounded investigative support only. Not a determination
              of guilt or legal conclusion.
            </p>
          </div>
          <Status tone="neutral">Read only</Status>
        </div>
        <div className="assistant-layout">
          <aside className="assistant-context">
            <div className="eyebrow">ACTIVE SCOPE</div>
            <h2>{record?.caseNumber || "No authorized case"}</h2>
            <p>
              Retrieval must apply role, case assignment, classification, and
              active grants before any evidence enters model context.
            </p>
            <dl>
              <dt>Mode</dt>
              <dd>{activeBrief?.mode?.replaceAll("_", " ") || "Workspace brief"}</dd>
              <dt>Source</dt>
              <dd>
                {source === "question" ? "Question response" : "Generated case brief"}
              </dd>
            </dl>
            {record && <Link href={`/cases/${encodeURIComponent(record.caseNumber)}`}>Open workspace ↗</Link>}
          </aside>
          <main className="assistant-main">
            <form className="ask-box" onSubmit={ask}>
              <span>/case {record?.caseNumber || "unavailable"}</span>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                aria-label="Question for case assistant"
              />
              <div>
                <div className="prompt-chips">
                  {prompts.map((prompt) => (
                    <button
                      type="button"
                      key={prompt}
                      onClick={() => setQuestion(prompt)}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
                <button className="primary-button" disabled={busy}>
                  {busy ? "Checking sources…" : "Ask case →"}
                </button>
              </div>
            </form>
            {(error || caseError) && (
              <div className="service-notice">
                <b>AI service unavailable</b>
                <p>{error || caseError}</p>
              </div>
            )}
            {activeBrief ? (
              <section className="answer-card">
                <div className="answer-head">
                  <div>
                    <div className="eyebrow">AUTHORIZED RESPONSE</div>
                    <h2>Case brief</h2>
                  </div>
                  <Status tone="good">
                    {source === "question" ? "Question response" : "Generated brief"}
                  </Status>
                </div>
                <p className="answer-overview">
                  {activeBrief.answer ||
                    activeBrief.caseOverview ||
                    "The service returned no overview."}
                </p>
                <div className="claim-list">
                  {activeBrief.claims?.map((claim, index) => (
                    <article key={`${claim.claim}-${index}`}>
                      <span className="claim-index">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <div>
                        <p>{claim.claim}</p>
                        <div className="claim-meta">
                          <Status
                            tone={
                              claim.status === "SUPPORTED" ? "good" : "warning"
                            }
                          >
                            {claim.status}
                          </Status>
                          {claim.sources?.map((sourceItem) => (
                            <Link
                              className="citation"
                              key={`${sourceItem.documentId}-${sourceItem.page}`}
                              href={`/documents?source=${encodeURIComponent(sourceItem.documentId)}`}
                              title="Open the authorized document register"
                            >
                              {sourceItem.documentTitle || sourceItem.documentId} · Page{" "}
                              {sourceItem.page || "—"}
                            </Link>
                          ))}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
                {!activeBrief.claims?.length && (
                  <div className="inline-empty">
                    No supported factual claims were returned.
                  </div>
                )}
                {!!activeBrief.contradictions?.length && (
                  <section className="analysis-flags" aria-label="Detected contradictions">
                    <div className="eyebrow">REVIEW FLAGS</div>
                    {activeBrief.contradictions.map((item, index) => (
                      <article key={`${item.type}-${index}`}>
                        <b>{item.type?.replaceAll("_", " ") || "Evidence discrepancy"}</b>
                        <p>{item.description || "Authorized sources contain conflicting facts."}</p>
                      </article>
                    ))}
                  </section>
                )}
                {!!activeBrief.missingInformation?.length && (
                  <section className="missing-info" aria-label="Missing information">
                    <div className="eyebrow">MISSING INFORMATION</div>
                    <ul>{activeBrief.missingInformation.map((item) => <li key={item}>{item}</li>)}</ul>
                  </section>
                )}
              </section>
            ) : (
              <div className="inline-empty">
                {caseLoading || loadingBrief
                  ? "Building the authorized case brief…"
                  : "No authorized case brief is available."}
              </div>
            )}
          </main>
        </div>
      </div>
    </AppShell>
  );
}
