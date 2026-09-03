import base64
import hashlib
import html
import io
import secrets
from datetime import timedelta
import qrcode
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import get_settings
from ..models import AuditEvent, Case, Document, DocumentVersion, Evidence, EvidenceCustodyEvent, MerkleBatch, MerkleLeaf, VerificationToken
from ..security.auth import AuthenticatedUser
from ..security.policy import policy_engine
from ..security.signatures import SignatureService
from .verification_service import VerificationService
from ..utils.time import utc_now


class VerificationReportService:
    REPORT_ROLES = {"INVESTIGATING_OFFICER", "SUPERVISOR", "PROSECUTOR", "COURT_USER", "AUDITOR", "ADMIN"}

    def generate(self, db: Session, actor: AuthenticatedUser, case_number: str) -> str:
        if actor.role not in self.REPORT_ROLES:
            raise HTTPException(status_code=403, detail="Role cannot generate court verification reports")
        case = db.scalar(select(Case).where(Case.case_number == case_number))
        if not case or not policy_engine.can_view_case(db, actor, case):
            raise HTTPException(status_code=404, detail="Case not found")
        documents = [item for item in db.scalars(select(Document).where(Document.case_id == case.id)) if policy_engine.can_view_document(db, actor, item)]
        pairs = [(item, db.get(DocumentVersion, item.current_version_id)) for item in documents if item.current_version_id]
        pairs = [(document, version) for document, version in pairs if version]
        versions = [version for _, version in pairs]
        evidence = [item for item in db.scalars(select(Evidence).where(Evidence.case_id == case.id))
                    if policy_engine.can_view_evidence(db, actor, item)]
        evidence_ids = [item.id for item in evidence]
        custody = list(db.scalars(select(EvidenceCustodyEvent).where(EvidenceCustodyEvent.evidence_id.in_(evidence_ids)).order_by(EvidenceCustodyEvent.event_time))) if evidence_ids else []
        latest_batch = db.scalar(select(MerkleBatch).join(MerkleLeaf, MerkleLeaf.batch_id == MerkleBatch.id)
                                 .join(AuditEvent, AuditEvent.id == MerkleLeaf.event_id)
                                 .where(AuditEvent.case_id == case.id).order_by(MerkleBatch.batch_number.desc()))
        integrity_results = [VerificationService().verify_registered_version(db, version) for version in versions]
        hash_verified = bool(versions) and all(result["hashVerified"] for result in integrity_results)
        signature_verified = bool(versions) and all(result["signatureVerified"] for result in integrity_results)
        version_verified = True
        for document in documents:
            chain = list(db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == document.id).order_by(DocumentVersion.version_number)))
            if not chain or document.current_version_id != chain[-1].id:
                version_verified = False
                break
            for index in range(1, len(chain)):
                if chain[index].previous_version_hash != chain[index - 1].sha256_original:
                    version_verified = False
                    break
        anchor_verified = bool(latest_batch and latest_batch.anchor_status in {"VERIFIED_PUBLIC", "ANCHORED"})
        integrity_status = "VERIFIED" if all((hash_verified, signature_verified, version_verified, anchor_verified)) else "VERIFICATION WARNING"
        signature_valid = sum(1 for result in integrity_results if result["signatureVerified"])
        raw_token = secrets.token_urlsafe(32)
        token = VerificationToken(token_hash=hashlib.sha256(raw_token.encode()).hexdigest(), case_id=case.id,
                                  created_by=actor.id, expires_at=utc_now() + timedelta(days=7),
                                  hash_verified=hash_verified, signature_verified=signature_verified,
                                  version_verified=version_verified, anchor_verified=anchor_verified)
        db.add(token); db.flush()
        public_url = f"{get_settings().api_url}/api/v1/public/verify/{raw_token}"
        image = qrcode.make(public_url); buffer = io.BytesIO(); image.save(buffer, format="PNG")
        qr_data = base64.b64encode(buffer.getvalue()).decode()
        db.add(AuditEvent(actor_user_id=actor.id, organization_id=actor.organization_id, action="GENERATE_VERIFICATION_REPORT",
                          resource_type="CASE", resource_id=case.id, case_id=case.id, authorization_decision="ALLOWED",
                          metadata_json={"verification_token_id": token.id, "expires_at": token.expires_at.isoformat()}))
        db.commit()
        rows = "".join(f"<tr><td>{html.escape(document.title)}</td><td>V{version.version_number}</td><td><code>{version.sha256_original}</code></td><td>{'VERIFIED' if SignatureService().verify_version(db, version) else 'UNVERIFIED'}</td></tr>"
                       for document, version in pairs)
        custody_rows = "".join(f"<tr><td>{html.escape(event.event_type)}</td><td>{event.event_time.isoformat()}</td><td><code>{event.event_hash}</code></td></tr>" for event in custody)
        anchor = f"{latest_batch.anchor_status} · {latest_batch.merkle_root}" if latest_batch else "Checkpoint pending"
        return f"""<!doctype html><html><head><meta charset='utf-8'><title>NyayaGraph Verification Report</title>
<style>body{{font:14px system-ui;color:#172234;max-width:1000px;margin:40px auto;padding:0 24px}}h1{{color:#0c3540}}table{{width:100%;border-collapse:collapse;margin:16px 0}}th,td{{border:1px solid #cad3d8;padding:8px;text-align:left}}code{{font-size:11px;word-break:break-all}}.status{{padding:12px;border-left:4px solid #16806f;background:#eef8f5}}.qr{{width:150px}}</style></head><body>
<p>NYAYAGRAPH · COURT VERIFICATION PACKAGE</p><h1>{html.escape(case.case_number)}</h1><p>{html.escape(case.title)}</p>
<div class='status'><b>Integrity status:</b> {integrity_status}<br>Documents signed: {signature_valid}/{len(versions)}<br>Generated: {utc_now().isoformat()}Z</div>
<h2>Section-63-supporting metadata</h2><p>This report supplies electronic-evidence verification metadata. It does not claim automatic admissibility or automatic certification.</p>
<table><thead><tr><th>Document</th><th>Version</th><th>SHA-256</th><th>Signature</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Custody events</h2><table><thead><tr><th>Event</th><th>Time</th><th>Event hash</th></tr></thead><tbody>{custody_rows}</tbody></table>
<h2>Merkle/public checkpoint</h2><p>{html.escape(anchor)}</p><img class='qr' alt='Public authenticity verification QR' src='data:image/png;base64,{qr_data}'><p><a href='{html.escape(public_url)}'>Verify authenticity</a>. Public verification reveals authenticity status only and expires in seven days.</p>
</body></html>"""

    def public_verify(self, db: Session, raw_token: str) -> dict:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        token = db.scalar(select(VerificationToken).where(VerificationToken.token_hash == token_hash, VerificationToken.expires_at > utc_now()))
        if not token:
            raise HTTPException(status_code=404, detail="Verification token is invalid or expired")
        authentic = token.hash_verified and token.signature_verified and token.version_verified and token.anchor_verified
        return {"status": "DOCUMENT_AUTHENTIC" if authentic else "VERIFICATION_WARNING",
                "hashVerified": token.hash_verified, "signatureVerified": token.signature_verified,
                "versionVerified": token.version_verified, "anchorVerified": token.anchor_verified}
