import hashlib

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app.models import AuditEvent, Case, Document, Evidence, MerkleBatch, MerkleLeaf, Organization, User
from app.security.auth import AuthenticatedUser
from app.security.policy import policy_engine
from app.services.merkle_service import MerkleCheckpointService
from app.seed import run as seed


def actor(user: User, *, role: str | None = None, organization_id: str | None = None) -> AuthenticatedUser:
    return AuthenticatedUser(id=user.id, organization_id=organization_id or user.organization_id,
                             name=user.name, email=user.email, role=role or user.role,
                             clearance_level=user.clearance_level)


def test_supervisor_and_auditor_roles_do_not_bypass_organization_scope():
    seed(reset=True)
    with SessionLocal() as db:
        case = db.query(Case).filter_by(case_number="MH-PUNE-2026-00142").one()
        document = db.query(Document).filter_by(case_id=case.id).first()
        user = db.query(User).filter_by(email="auditor@nyaya.local").one()
        foreign_org = Organization(name="Out-of-scope organization", type="POLICE", status="ACTIVE")
        db.add(foreign_org); db.flush()

        supervisor = actor(user, role="SUPERVISOR", organization_id=foreign_org.id)
        auditor = actor(user, role="AUDITOR", organization_id=foreign_org.id)
        assert policy_engine.can_view_case(db, supervisor, case) is False
        assert policy_engine.can_view_document(db, supervisor, document) is False
        assert policy_engine.can_view_case(db, auditor, case) is False


def test_linked_restricted_document_hides_evidence_from_every_evidence_policy_path():
    seed(reset=True)
    with SessionLocal() as db:
        case = db.query(Case).filter_by(case_number="MH-PUNE-2026-00142").one()
        io = db.query(User).filter_by(email="io@nyaya.local").one()
        expert = db.query(User).filter_by(email="expert@nyaya.local").one()
        evidence = Evidence(case_id=case.id, evidence_code="RESTRICTED-EVIDENCE-01", evidence_type="STATEMENT",
                            description="Restricted linked evidence", classification_level=3, status="REGISTERED")
        db.add(evidence); db.flush()
        db.add(Document(case_id=case.id, evidence_id=evidence.id, document_type="WITNESS_STATEMENT",
                        title="Restricted linked evidence", classification_level=3,
                        created_by=io.id, storage_policy="PRIVATE_VAULT"))
        db.flush()
        assert policy_engine.can_view_evidence(db, actor(expert), evidence) is False


def test_merkle_proof_requires_access_to_its_case():
    seed(reset=True)
    with SessionLocal() as db:
        existing_user = db.query(User).filter_by(email="io@nyaya.local").one()
        expert = db.query(User).filter_by(email="expert@nyaya.local").one()
        other_case = Case(case_number="MH-OTHER-2026-00001", title="Other jurisdiction case",
                          description="Case outside the requesting user's assignment.", case_type="TEST",
                          status="ACTIVE", jurisdiction="Other", classification_level=2,
                          fir_number="OTHER-FIR", police_station="Other", investigating_officer_id=existing_user.id)
        db.add(other_case); db.flush()
        event = AuditEvent(actor_user_id=existing_user.id, organization_id=existing_user.organization_id,
                           action="CASE_VIEW", resource_type="CASE", resource_id=other_case.id,
                           case_id=other_case.id, authorization_decision="ALLOWED")
        db.add(event); db.flush()
        leaf_hash = hashlib.sha256(b"other-case-event").hexdigest()
        batch = MerkleBatch(batch_number=9999, merkle_root=leaf_hash, event_count=1, anchor_status="PENDING")
        db.add(batch); db.flush()
        db.add(MerkleLeaf(batch_id=batch.id, event_type=event.action, event_id=event.id,
                          leaf_hash=leaf_hash, leaf_index=0))
        db.flush()

        with pytest.raises(HTTPException) as denied:
            MerkleCheckpointService().proof(db, actor(expert), event.id)
        assert denied.value.status_code == 404
