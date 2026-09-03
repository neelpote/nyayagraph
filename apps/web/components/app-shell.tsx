"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearSession, getSession } from "@/lib/auth";
import { useEffect, useState } from "react";
import {
  ArrowLeftRight, BadgeCheck, ExternalLink, FileStack, Fingerprint,
  KeyRound, LayoutDashboard, LogOut, Menu, Network, Search, Sparkles, ScrollText,
} from "lucide-react";

const nav = [
  [LayoutDashboard, "Dashboard", "/dashboard"],
  [Search, "Cases", "/cases"],
  [FileStack, "Documents", "/documents"],
  [Fingerprint, "Evidence", "/evidence"],
  [ArrowLeftRight, "Custody", "/custody"],
  [Sparkles, "AI Assistant", "/ai"],
  [BadgeCheck, "Verification", "/verification"],
  [ScrollText, "Audit logs", "/audit"],
  [KeyRound, "Access", "/access"],
  [Network, "Integrations", "/integrations"],
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [session, setSession] = useState<ReturnType<typeof getSession>>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const storedSession = getSession();
      setSession(storedSession);
      setReady(true);
      if (!storedSession) router.replace("/login");
    }, 0);
    return () => window.clearTimeout(timer);
  }, [router]);
  if (!ready || !session)
    return <div className="page-loading">Loading secure workspace…</div>;
  const signOut = () => {
    clearSession();
    setSession(null);
    router.replace("/login");
  };
  const isActive = (href: string) =>
    path === href || path.startsWith(`${href}/`);
  return (
    <div className="shell">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard">
          <span className="brand-mark">N</span>
          <span>
            Nyaya<span>Graph</span>
            <small>CASE INTELLIGENCE</small>
          </span>
        </Link>
        <nav>
          {nav.map(([Icon, label, href]) => (
            <Link
              key={href}
              href={href}
              aria-current={isActive(href) ? "page" : undefined}
              className={isActive(href) ? "nav-item active" : "nav-item"}
              title={label}
            >
              <Icon aria-hidden="true" />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-stub">
            <span>{session.user.name?.slice(0, 1) || "U"}</span>
            <div>
              <b>{session.user.name || session.user.email}</b>
              <small>{session.user.role.replaceAll("_", " ")}</small>
            </div>
          </div>
          <button
            className="quiet-button"
            onClick={signOut}
          >
            <LogOut aria-hidden="true" /> Sign out
          </button>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <details className="mobile-menu">
            <summary aria-label="Open navigation"><Menu aria-hidden="true" /></summary>
            <nav>
              {nav.map(([Icon, label, href]) => (
                <Link key={href} href={href} aria-current={isActive(href) ? "page" : undefined}>
                  <Icon aria-hidden="true" /> {label}
                </Link>
              ))}
              <button onClick={signOut}><LogOut aria-hidden="true" /> Sign out</button>
            </nav>
          </details>
          <div className="secure-line">
            <span className="pulse" /> SECURE CASEWORK ENVIRONMENT <em>•</em>{" "}
            DEVELOPMENT DEMO
          </div>
          <div className="top-actions">
            <span className="role-badge">
              {session.user.role.replaceAll("_", " ")}
            </span>
            <Link href="/cases" className="case-jump">
              Open a case <ExternalLink aria-hidden="true" />
            </Link>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
