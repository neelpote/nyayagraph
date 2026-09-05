export function Status({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "good" | "warning" | "danger" | "neutral" }) { return <span className={`status ${tone}`}>{children}</span>; }
export function Hash({ value }: { value?: string | number | boolean | null }) { return <code className="hash">{value ? String(value) : "Pending external synchronization"}</code>; }
