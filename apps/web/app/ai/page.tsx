"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Status } from "@/components/status";
import { api } from "@/lib/api";
import type { AIBrief } from "@/lib/types";
import { trustLabel, trustTone } from "@/lib/types";
import { useAuthorizedCase } from "@/hooks/use-authorized-case";

const prompts = [
  "Summarize this case.",
  "Show all timing contradictions.",
  "What forensic findings are available?",
  "Where was the vehicle first reported?",
  "Are there conflicting witness accounts?",
];

/** Map a generationMode string to a readable label. */
function modeLabel(mode?: string): string {
  if (mode === "GROUNDED_LLM") return "Qwen3-8B — Evidence-grounded";
  if (mode === "DETERMINISTIC_DEMO") return "Deterministic demo";
  return "Workspace brief";
}

/** Map claim status to a tone the Status component understands. */
function claimTone(status: string): "good" | "warning" | "neutral" | "danger" {
  if (status === "SUPPORTED") return "good";
  if (status === "PARTIALLY_SUPPORTED" || status === "CONFLICTING") return "warning";
  if (status === "UNSUPPORTED") return "danger";
  return "neutral";
}

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

  const activeBrief = brief;
  const responseStatus = activeBrief?.trustStatus ?? activeBrief?.status;
  const responseTone = trustTone(responseStatus);
  const responseLabel = trustLabel(responseStatus);

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
          {/* Sidebar */}
          <aside className="assistant-context">
            <div className="eyebrow">ACTIVE SCOPE</div>
            <h2>{record?.caseNumber || "No authorized case"}</h2>
            <p>
              Retrieval applies role, case assignment, classification, and
              active grants before any evidence enters model context.
            </p>
            <dl>
              <dt>Mode</dt>
              <dd>{modeLabel(activeBrief?.generationMode)}</dd>
              <dt>Source</dt>
              <dd>
                {source === "question" ? "Question response" : "Generated case brief"}
              </dd>
              {responseStatus && (
                <>
                  <dt>Evidence support</dt>
                  <dd>
                    <Status tone={responseTone}>{responseLabel}</Status>
                  </dd>
                </>
              )}
            </dl>
            {record && (
              <Link href={`/cases/${encodeURIComponent(record.caseNumber)}`}>
                Open workspace ↗
              </Link>
            )}
          </aside>

          {/* Main content */}
          <main className="assistant-main">
            {/* Question form */}
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

            {/* Error state */}
            {(error || caseError) && (
              <div className="service-notice">
                <b>AI service unavailable</b>
                <p>{error || caseError}</p>
              </div>
            )}

            {/* Response card */}
            {activeBrief ? (
              <section className="answer-card">
                {/* Header row */}
                <div className="answer-head">
                  <div>
                    <div className="eyebrow">AUTHORIZED RESPONSE</div>
                    <h2>
                      {source === "question" ? "Question response" : "Case brief"}
                    </h2>
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                    {/* Trust status badge */}
                    {responseStatus && (
                      <Status tone={responseTone}>{responseLabel}</Status>
                    )}
                    {/* Generation mode badge */}
                    {activeBrief.generationMode && (
                      <Status tone={activeBrief.generationMode === "GROUNDED_LLM" ? "good" : "neutral"}>
                        {activeBrief.generationMode === "GROUNDED_LLM" ? "Qwen3-8B" : "Demo mode"}
                      </Status>
                    )}
                  </div>
                </div>

                {/* Natural-language answer */}
                <p className="answer-overview">
                  {activeBrief.answer ||
                    activeBrief.caseOverview ||
                    "The service returned no overview."}
                </p>

                {/* Evidence support summary */}
                {activeBrief.claims && activeBrief.claims.length > 0 && (
                  <p className="evidence-support-summary">
                    {(() => {
                      const supported = activeBrief.claims!.filter(
                        (c) => c.status === "SUPPORTED"
                      ).length;
                      const total = activeBrief.claims!.length;
                      const sourceCount = activeBrief.claims!.reduce(
                        (sum, c) => sum + (c.sources?.length ?? 0),
                        0
                      );
                      if (supported === total && total > 0)
                        return `✓ Strongly supported by ${sourceCount} source${sourceCount !== 1 ? "s" : ""}`;
                      if (supported > 0)
                        return `~ Partially supported — ${supported}/${total} claims verified`;
                      return "⚠ Insufficient or conflicting evidence";
                    })()}
                  </p>
                )}

                {/* Claim list */}
                <div className="claim-list">
                  {activeBrief.claims?.map((claim, index) => (
                    <article key={`${claim.claim}-${index}`}>
                      <span className="claim-index">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <div>
                        <p>{claim.claim}</p>
                        <div className="claim-meta">
                          <Status tone={claimTone(claim.status)}>
                            {/* Human-readable status label */}
                            {claim.status === "SUPPORTED"
                              ? "Supported"
                              : claim.status === "PARTIALLY_SUPPORTED"
                              ? "Partially supported"
                              : claim.status === "CONFLICTING"
                              ? "Conflicting evidence"
                              : claim.status === "UNSUPPORTED"
                              ? "Unsupported"
                              : "Insufficient evidence"}
                          </Status>
                          {/* Citations ? click opens the document viewer */}
                          {claim.sources?.map((src) => (
                            <Link
                              className="citation"
                              key={`${src.documentId}-${src.page}`}
                              href={`/documents?source=${encodeURIComponent(src.documentId)}`}
                              title={`Open ${src.documentTitle || src.documentId} in document register`}
                            >
                              {src.documentTitle || src.documentId}
                              {src.page ? ` · p. ${src.page}` : ""}
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

                {/* Contradictions */}
                {!!activeBrief.contradictions?.length && (
                  <section
                    className="analysis-flags"
                    aria-label="Detected contradictions"
                  >
                    <div className="eyebrow">REVIEW FLAGS — CONFLICTING EVIDENCE</div>
                    {activeBrief.contradictions.map((item, index) => (
                      <article key={`${item.type}-${index}`}>
                        <b>
                          {item.type?.replaceAll("_", " ") ||
                            "Evidence discrepancy"}
                        </b>
                        <p>
                          {item.description ||
                            "Authorized sources contain conflicting facts. NyayaGraph does not determine which source is truthful."}
                        </p>
                        {/* Contradiction source citations */}
                        {item.sources && item.sources.length > 0 && (
                          <div className="claim-meta" style={{ marginTop: "0.25rem" }}>
                            {item.sources.map((src) => (
                              <Link
                                className="citation"
                                key={`${src.documentId}-${src.page}`}
                                href={`/documents?source=${encodeURIComponent(src.documentId)}`}
                                title={`Open ${src.documentTitle || src.documentId}`}
                              >
                                {src.documentTitle || src.documentId}
                                {src.page ? ` · p. ${src.page}` : ""}
                              </Link>
                            ))}
                          </div>
                        )}
                      </article>
                    ))}
                  </section>
                )}

                {/* Missing information */}
                {!!activeBrief.missingInformation?.length && (
                  <section
                    className="missing-info"
                    aria-label="Missing information"
                  >
                    <div className="eyebrow">MISSING INFORMATION</div>
                    <ul>
                      {activeBrief.missingInformation.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </section>
                )}

                {/* Disclaimer */}
                {activeBrief.disclaimer && (
                  <p
                    className="answer-disclaimer"
                    style={{
                      fontSize: "0.75rem",
                      opacity: 0.6,
                      marginTop: "1rem",
                      fontStyle: "italic",
                    }}
                  >
                    {activeBrief.disclaimer}
                  </p>
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
