"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { saveSession } from "@/lib/auth";

const people = [
  ["io@nyaya.local", "INVESTIGATING OFFICER"], ["fsl@nyaya.local", "FSL OFFICER"], ["expert@nyaya.local", "EXTERNAL EXPERT"], ["auditor@nyaya.local", "AUDITOR"]
];
const demoPassword = "NyayaDemo!2026";
export default function LoginPage() {
  const router = useRouter(); const [email, setEmail] = useState("io@nyaya.local"); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function login(e: React.FormEvent) { e.preventDefault(); setBusy(true); setError(""); try { saveSession(await api.login(email, password)); router.push("/dashboard"); } catch (err) { setError(err instanceof Error ? err.message : "Unable to sign in."); } finally { setBusy(false); } }
  return <main className="login-page"><section className="login-art"><div className="brand"><span className="brand-mark">N</span><span>Nyaya<span>Graph</span><small>CASE INTELLIGENCE</small></span></div><div className="login-art-copy"><div className="eyebrow">SECURE JUSTICE WORKFLOWS</div><h1>From case files<br/>to verifiable<br/><em>intelligence.</em></h1><p>One accountable workspace for evidence, provenance and investigative context.</p></div><div className="evidence-lattice"><span>DOCUMENT</span><i>SHA-256</i><span>PROVENANCE</span><i>MERKLE</i><span>VERIFIED</span></div></section><section className="login-panel"><div className="login-form-wrap"><div className="eyebrow">AUTHORIZED ACCESS</div><h2>Enter casework</h2><p>Use a seeded development account to explore the NyayaGraph MVP.</p><form onSubmit={login}><label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" required /></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" required /></label>{error && <div className="form-error">{error}</div>}<button className="primary-button full" disabled={busy}>{busy ? "Authenticating?" : "Access workspace ?"}</button></form><div className="demo-accounts"><span>DEMO IDENTITIES</span>{people.map(([account, role]) => <button key={account} type="button" onClick={() => { setEmail(account); setPassword(demoPassword); }}><b>{account}</b><small>{role}</small></button>)}</div><small className="legal">Development access only. Every case action is audited.</small></div></section></main>;
}
