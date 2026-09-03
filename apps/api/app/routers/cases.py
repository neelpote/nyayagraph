import hashlib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..security.auth import AuthenticatedUser, get_current_user
from ..security.policy import policy_engine
from ..services.case_service import CaseService
from ..services.audit_service import AuditService
from ..blockchain.ledger import get_ledger
from ..models import Case, CaseAssignment

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseCreate(BaseModel):
    case_number: str = Field(min_length=5, max_length=120)
    title: str = Field(min_length=5, max_length=250)
    description: str = Field(min_length=10, max_length=4000)
    case_type: str = Field(min_length=2, max_length=100)
    jurisdiction: str = Field(min_length=2, max_length=160)
    fir_number: str = Field(min_length=2, max_length=120)
    police_station: str = Field(min_length=2, max_length=160)
    classification_level: int = Field(default=2, ge=1, le=4)


@router.post("")
def create_case(payload: CaseCreate, actor: AuthenticatedUser = Depends(get_current_user),
                db: Session = Depends(get_db)):
    if actor.role not in {"INVESTIGATING_OFFICER", "SUPERVISOR", "ADMIN"}:
        raise HTTPException(status_code=403, detail="Role cannot create a case")
    if db.scalar(select(Case.id).where(Case.case_number == payload.case_number)):
        raise HTTPException(status_code=409, detail="Case number already exists")
    case = Case(**payload.model_dump(), status="INVESTIGATION_ACTIVE",
                investigating_officer_id=actor.id)
    db.add(case); db.flush()
    db.add(CaseAssignment(case_id=case.id, user_id=actor.id, assignment_role="LEAD_INVESTIGATOR"))
    commitment = hashlib.sha256(case.case_number.encode()).hexdigest()
    transaction = get_ledger().register_case(db, case_id=case.id, case_commitment=commitment,
                                              actor_id=actor.id, organization_id=actor.organization_id)
    db.commit()
    return {"id": case.id, "caseNumber": case.case_number, "status": case.status,
            "provenance": {"transaction": transaction,
                           "mode": "FABRIC" if not transaction.startswith("dev-ledger-") else "DATABASE_DEV"}}


@router.get("")
def list_cases(actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..repositories.core import CaseRepository
    from ..security.policy import policy_engine
    cases = CaseRepository().list(db)
    return [{"caseNumber": case.case_number, "title": case.title, "type": case.case_type, "status": case.status,
             "updatedAt": case.updated_at, "integrity": CaseService().workspace(db, actor, case.case_number)["integrity"]}
            for case in cases if policy_engine.can_view_case(db, actor, case)]


@router.get("/{case_number}")
def get_case(case_number: str, actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    result = CaseService().workspace(db, actor, case_number)
    AuditService().record(db, actor, action="CASE_VIEW", resource_type="CASE",
                          resource_id=result["id"], case_id=result["id"])
    return result


@router.get("/{case_number}/timeline")
def timeline(case_number: str, actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..ai.contradictions import FactExtractionService
    from ..ai.corpus import AuthorizedCorpus
    from ..models import CaseTimelineEvent, Document, DocumentVersion, Evidence, EvidenceCustodyEvent
    case = db.scalar(select(Case).where(Case.case_number == case_number))
    if not case or not policy_engine.can_view_case(db, actor, case):
        raise HTTPException(status_code=404, detail="Case not found")
    result = []
    for item in db.scalars(select(CaseTimelineEvent).where(CaseTimelineEvent.case_id == case.id)):
        if item.source_document_version_id:
            version = db.get(DocumentVersion, item.source_document_version_id)
            document = db.get(Document, version.document_id) if version else None
            if not document or not policy_engine.can_view_document(db, actor, document):
                continue
        if item.evidence_id:
            source_evidence = db.get(Evidence, item.evidence_id)
            if not source_evidence or not policy_engine.can_view_evidence(db, actor, source_evidence):
                continue
        result.append({"time": item.event_time, "title": item.title,
                       "description": item.description, "state": "VERIFIED"})
    for fact in FactExtractionService().extract(AuthorizedCorpus().for_case(db, actor, case)) if case.incident_time else []:
        result.append({"time": case.incident_time.replace(hour=fact.minutes // 60, minute=fact.minutes % 60),
                       "title": fact.source.document_title, "description": fact.source.text, "state": "SOURCE_REPORTED"})
    visible_evidence = [item for item in db.scalars(select(Evidence).where(Evidence.case_id == case.id))
                        if policy_engine.can_view_evidence(db, actor, item)]
    for item in visible_evidence:
        result.append({"time": item.capture_time, "title": f"Evidence {item.evidence_code} captured",
                       "description": item.description, "state": "REGISTERED"})
        for event in db.scalars(select(EvidenceCustodyEvent).where(EvidenceCustodyEvent.evidence_id == item.id)):
            result.append({"time": event.event_time, "title": f"{item.evidence_code} {event.event_type.replace('_', ' ').title()}",
                           "description": event.purpose, "state": "LEDGER_RECORDED" if event.fabric_tx_id else "PENDING_LEDGER"})
    return sorted(result, key=lambda item: item["time"])


@router.get("/{case_number}/graph")
def graph(case_number: str, actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..graph.service import GraphService
    return GraphService().case_graph(db, actor, case_number)
