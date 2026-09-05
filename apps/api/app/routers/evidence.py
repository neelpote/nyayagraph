from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AuditEvent, Case, Document, DocumentVersion, Evidence, EvidenceCustodyEvent, MerkleBatch, MerkleLeaf, Organization, User
from ..security.auth import AuthenticatedUser, get_current_user
from ..security.policy import policy_engine
from ..services.custody_service import CustodyService
from ..services.verification_service import VerificationService
from ..services.audit_service import AuditService

router = APIRouter(prefix="/evidence", tags=["evidence"])


class CustodyTransferRequest(BaseModel):
    to_org_id: str
    purpose: str = Field(min_length=10, max_length=500)
    location: str = Field(min_length=2, max_length=250)


@router.get("")
def list_evidence(actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    visible = []
    for evidence in db.scalars(select(Evidence).order_by(Evidence.evidence_code)):
        case = db.get(Case, evidence.case_id)
        if not case or not policy_engine.can_view_evidence(db, actor, evidence):
            continue
        visible.append({"id": evidence.id, "code": evidence.evidence_code, "type": evidence.evidence_type,
                        "description": evidence.description, "status": evidence.status,
                        "caseNumber": case.case_number, "captureTime": evidence.capture_time})
    return visible


@router.get("/{evidence_id}/passport")
def passport(evidence_id: str, actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    evidence = db.scalar(select(Evidence).where((Evidence.id == evidence_id) | (Evidence.evidence_code == evidence_id)))
    if not evidence or not policy_engine.can_view_evidence(db, actor, evidence):
        raise HTTPException(status_code=404, detail="Evidence not found")
    case = db.get(Case, evidence.case_id)
    document = db.scalar(select(Document).where(Document.evidence_id == evidence.id))
    if not case:
        raise HTTPException(status_code=404, detail="Evidence not found")
    version = db.get(DocumentVersion, document.current_version_id) if document and document.current_version_id else None
    creator = db.get(User, version.created_by) if version else None
    creator_organization = db.get(Organization, creator.organization_id) if creator else None
    custodian = db.get(Organization, evidence.current_custodian_org_id) if evidence.current_custodian_org_id else None
    events = list(db.scalars(select(EvidenceCustodyEvent).where(EvidenceCustodyEvent.evidence_id == evidence.id).order_by(EvidenceCustodyEvent.event_time)))
    custody_warning = any((right.event_time - left.event_time).total_seconds() > 3 * 60 * 60
                          for left, right in zip(events, events[1:]))
    batch = db.scalar(select(MerkleBatch).join(MerkleLeaf, MerkleLeaf.batch_id == MerkleBatch.id)
                      .join(AuditEvent, AuditEvent.id == MerkleLeaf.event_id)
                      .where(AuditEvent.case_id == case.id, AuditEvent.resource_id == evidence.id)
                      .order_by(MerkleBatch.batch_number.desc()))
    verification = VerificationService().verify_registered_version(db, version) if version else {"hashVerified": False, "signatureVerified": False}
    result = {"evidenceId": evidence.evidence_code, "caseId": case.case_number, "sha256Original": version.sha256_original if version else "pending",
            "sha256Encrypted": version.sha256_encrypted if version else "pending", "creatorOrganization": creator_organization.name if creator_organization else None,
            "creatorRole": creator.role if creator else None, "captureTimestamp": evidence.capture_time, "ingestionTimestamp": version.created_at if version else None,
            "version": version.version_number if version else 0, "custodian": custodian.name if custodian else "Unassigned",
            "classification": "RESTRICTED" if evidence.classification_level >= 3 else "CONFIDENTIAL", "signatureVerified": verification["signatureVerified"],
            "hashVerified": verification["hashVerified"], "custodyStatus": "WARNING" if custody_warning else "VERIFIED",
            "fabricTransaction": events[-1].fabric_tx_id if events else None,
            "merkleBatch": batch.batch_number if batch else None,
            "publicTransaction": batch.public_tx_hash if batch else None,
            "publicAnchorVerified": bool(batch and batch.anchor_status == "VERIFIED_PUBLIC"),
            "anchorStatus": batch.anchor_status if batch else "PENDING",
            "ledgerMode": ("FABRIC" if events and events[-1].fabric_tx_id and not events[-1].fabric_tx_id.startswith("dev-ledger-") else "DATABASE_DEV"),
            "storageBackend": version.storage_reference.split("://", 1)[0].upper() if version else None,
            "custodyHistory": [{"event": e.event_type, "time": e.event_time, "purpose": e.purpose, "hash": e.event_hash} for e in events]}
    AuditService().record(db, actor, action="EVIDENCE_PASSPORT_VIEW", resource_type="EVIDENCE",
                          resource_id=evidence.id, case_id=case.id)
    return result


@router.post("/{evidence_id}/custody")
def transfer_custody(evidence_id: str, payload: CustodyTransferRequest,
                     actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    event = CustodyService().transfer(db, actor, evidence_id, **payload.model_dump())
    return {"eventId": event.id, "evidenceId": event.evidence_id, "eventType": event.event_type,
            "fromOrganizationId": event.from_org_id, "toOrganizationId": event.to_org_id,
            "eventTime": event.event_time, "eventHash": event.event_hash,
            "previousEventHash": event.previous_event_hash, "fabricTransaction": event.fabric_tx_id}
