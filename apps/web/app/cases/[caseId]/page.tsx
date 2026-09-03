import { AppShell } from "@/components/app-shell";
import { CaseWorkspace } from "@/components/case-workspace";
export default async function CasePage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  return <AppShell><CaseWorkspace caseNumber={decodeURIComponent(caseId)} /></AppShell>;
}
