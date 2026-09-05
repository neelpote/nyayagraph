from __future__ import annotations

import re
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.contradictions import ContradictionEngine, FactExtractionService
from ..ai.corpus import AuthorizedCorpus, AuthorizedChunk
from ..models import AccessGrant, AuditEvent, Document, DocumentVersion, Evidence, EvidenceCustodyEvent, MerkleBatch, MerkleLeaf
from ..repositories.core import CaseRepository
from ..security.auth import AuthenticatedUser
from ..security.policy import policy_engine
from ..services.verification_service import VerificationService
from ..utils.time import utc_now


class IntegrityService:
    def case_integrity(self, db: Session, documents: list[Document], evidence: list[Evidence],
                       chunks: list[AuthorizedChunk]) -> dict:
        versions = [db.get(DocumentVersion, item.current_version_id) for item in documents if item.current_version_id]
        results = [VerificationService().verify_registered_version(db, version) for version in versions if version]
        custody_warnings = 0
        custody_count = 0
        custody_transactions: list[str] = []
        for item in evidence:
            events = list(db.scalars(select(EvidenceCustodyEvent).where(
                EvidenceCustodyEvent.evidence_id == item.id).order_by(EvidenceCustodyEvent.event_time)))
            custody_count += len(events)
            custody_transactions.extend(event.fabric_tx_id for event in events if event.fabric_tx_id)
            custody_warnings += sum(1 for left, right in zip(events, events[1:])
                                    if (right.event_time - left.event_time).total_seconds() > 3 * 60 * 60)
        registered_codes = {item.evidence_code.upper() for item in evidence}
        referenced_codes = {match.upper() for chunk in chunks for match in re.findall(r"\bE-\d{2,}\b", chunk.text, re.I)}
        missing = referenced_codes - registered_codes
        contradictions = ContradictionEngine().compare(FactExtractionService().extract(chunks))
        document_ids = [item.id for item in documents]
        expired_grants = len(list(db.scalars(select(AccessGrant).where(
            AccessGrant.resource_id.in_(document_ids), AccessGrant.status == "ACTIVE",
            AccessGrant.expires_at <= utc_now())))) if document_ids else 0
        case_id = documents[0].case_id if documents else (evidence[0].case_id if evidence else None)
        batch = db.scalar(select(MerkleBatch).join(MerkleLeaf, MerkleLeaf.batch_id == MerkleBatch.id)
                          .join(AuditEvent, AuditEvent.id == MerkleLeaf.event_id)
                          .where(AuditEvent.case_id == case_id).order_by(MerkleBatch.batch_number.desc())) if case_id else None
        fabric_transactions = [version.fabric_tx_id for version in versions if version and version.fabric_tx_id] + custody_transactions
        return {
            "documents": {"verified": sum(1 for result in results if result["hashVerified"]), "total": len(documents)},
            "custody": {"status": "WARNING" if custody_warnings else "VERIFIED", "warnings": custody_warnings},
            "signatures": {"valid": sum(1 for result in results if result["signatureVerified"]), "total": len(documents)},
            "missingAttachments": len(missing), "timelineDiscrepancies": len(contradictions),
            "expiredAccessGrants": expired_grants,
            "publicAnchorVerified": bool(batch and batch.anchor_status == "VERIFIED_PUBLIC"),
            "anchorStatus": batch.anchor_status if batch else "PENDING",
            "ledgerMode": "FABRIC" if any(not tx.startswith("dev-ledger-") for tx in fabric_transactions) else "DATABASE_DEV",
            "custodyEvents": custody_count,
        }


class CaseService:
    def __init__(self) -> None:
        self.repository = CaseRepository()
        self.integrity = IntegrityService()
        self.corpus = AuthorizedCorpus()

    def workspace(self, db: Session, actor: AuthenticatedUser, case_number: str) -> dict:
        case = self.repository.by_number(db, case_number)
        if not case:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Case not found")
        if not policy_engine.can_view_case(db, actor, case):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Case access denied")
        evidence = list(db.scalars(select(Evidence).where(Evidence.case_id == case.id)))
        visible_evidence = [item for item in evidence if policy_engine.can_view_evidence(db, actor, item)]
        documents = list(db.scalars(select(Document).where(Document.case_id == case.id)))
        authorized_docs = [doc for doc in documents if policy_engine.can_view_document(db, actor, doc)]
        chunks = self.corpus.for_case(db, actor, case)
        contradictions = ContradictionEngine().compare(FactExtractionService().extract(chunks))
        registered_codes = {item.evidence_code.upper() for item in visible_evidence}
        missing = sorted({match.upper() for chunk in chunks for match in re.findall(r"\bE-\d{2,}\b", chunk.text, re.I)} - registered_codes)
        alerts = [{"type": item.type, "message": item.explanation} for item in contradictions]
        alerts.extend({"type": "MISSING_ATTACHMENT", "message": f"A document references {code}, which is not registered."} for code in missing)
        for item in visible_evidence:
            events = list(db.scalars(select(EvidenceCustodyEvent).where(
                EvidenceCustodyEvent.evidence_id == item.id).order_by(EvidenceCustodyEvent.event_time)))
            for left, right in zip(events, events[1:]):
                gap_seconds = (right.event_time - left.event_time).total_seconds()
                if gap_seconds > 3 * 60 * 60:
                    hours, remainder = divmod(int(gap_seconds), 3600)
                    alerts.append({"type": "CUSTODY_WARNING", "message": f"Evidence {item.evidence_code} has a custody interval of {hours}h{remainder // 60:02d}m."})
        return {
            "id": case.id, "caseNumber": case.case_number, "title": case.title, "description": case.description,
            "caseType": case.case_type, "status": case.status, "jurisdiction": case.jurisdiction,
            "firNumber": case.fir_number, "policeStation": case.police_station, "incidentTime": case.incident_time,
            "incidentLocation": case.incident_location, "nextHearingAt": case.next_hearing_at, "updatedAt": case.updated_at,
            "evidence": [{"id": e.id, "code": e.evidence_code, "type": e.evidence_type, "description": e.description, "status": e.status} for e in visible_evidence],
            "documents": [{"id": d.id, "title": d.title, "type": d.document_type, "classification": d.classification_level,
                           "versionId": d.current_version_id} for d in authorized_docs],
            "integrity": self.integrity.case_integrity(db, authorized_docs, visible_evidence, chunks), "alerts": alerts,
            "aiBrief": {"status": "AVAILABLE_VIA_AUTHORIZED_AI_ENDPOINT",
                        "disclaimer": "Evidence-grounded investigative support only. Not a determination of guilt or legal conclusion."},
        }
