import argparse
import hashlib
from datetime import datetime, timedelta
from .bootstrap import main as bootstrap
from .database import SessionLocal
from .models import AccessGrant, AuditEvent, BlockchainAnchor, Case, CaseAssignment, Document, DocumentChunk, DocumentVersion, Evidence, EvidenceCustodyEvent, MerkleBatch, MerkleLeaf, Notification, Organization, OutboxEvent, Signature, User, VerificationToken
from .security.encryption import EncryptionService
from .security.signatures import SignatureService
from .storage.providers import get_storage_provider
from .security.passwords import hash_demo_password
from .utils.time import utc_now
from .blockchain.ledger import get_ledger
from .config import get_settings

DEMO_DOCUMENTS = [
    ("FIR", "FIR", 2, "FIR FIR-2026-PSH-881 records the reported theft of a blue Maruti Swift near Gate 3, Magarpatta Road on 14 August 2026. Investigation remains active."),
    ("Witness-01 statement", "WITNESS_STATEMENT", 2, "Witness-01 stated that the blue Swift departed Gate 3 at 21:20 on 14 August 2026."),
    ("Witness-02 statement", "WITNESS_STATEMENT", 2, "Witness-02 reported seeing a blue Swift near the access road shortly before 21:30."),
    ("Witness-03 statement — restricted", "WITNESS_STATEMENT", 3, "Witness-03 stated that the vehicle departed at approximately 22:05 on 14 August 2026."),
    ("CCTV-01 access road", "CCTV_REPORT", 2, "CCTV-01 records a blue Swift approaching the access road before the Gate 3 observation."),
    ("CCTV-02 Gate 3", "CCTV_REPORT", 2, "CCTV-02 records the blue Swift departing near Gate 3 at 21:27 on 14 August 2026."),
    ("Scene photograph 01", "PHOTOGRAPH", 2, "Scene photograph metadata records Gate 3, Magarpatta Road."),
    ("Vehicle photograph 02", "PHOTOGRAPH", 2, "Vehicle photograph metadata records a blue Maruti Swift."),
    ("Mobile extraction report", "MOBILE_EXTRACTION", 2, "The authorized mobile extraction report records device artifacts relevant to the vehicle-resale inquiry."),
    ("Call-detail analysis", "CALL_DETAIL_ANALYSIS", 2, "The authorized call-detail analysis records contacts for investigator review without determining guilt."),
    ("Seizure memo", "SEIZURE_MEMO", 2, "The seizure memo records recovered vehicle parts and their collection metadata."),
    ("Charge sheet", "CHARGE_SHEET", 2, "The demonstration charge sheet collates filed allegations and evidence references. It is not a determination of guilt."),
    ("Court order", "COURT_ORDER", 2, "The demonstration court order records the next procedural hearing and does not determine guilt."),
]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def run(reset: bool = False) -> None:
    password = get_settings().demo_password
    if not password:
        raise RuntimeError("DEMO_PASSWORD is required to create development identities")
    bootstrap()
    db = SessionLocal()
    try:
        if reset:
            for model in (OutboxEvent, VerificationToken, Notification, Signature, BlockchainAnchor, MerkleLeaf, MerkleBatch, AuditEvent, AccessGrant, EvidenceCustodyEvent, DocumentChunk, DocumentVersion, Document, Evidence, CaseAssignment, Case, User, Organization):
                db.query(model).delete()
            db.commit()
        if db.query(Case).filter_by(case_number="MH-PUNE-2026-00142").first():
            print("Seed dataset already exists")
            return
        police = Organization(name="Pune Police", type="POLICE", fabric_msp_id="PoliceMSP")
        fsl = Organization(name="Maharashtra FSL", type="FSL", fabric_msp_id="FSLMSP")
        db.add_all([police, fsl]); db.flush()
        io = User(id="11111111-1111-4111-8111-111111111111", external_identity_id="11111111-1111-4111-8111-111111111111", organization_id=police.id, name="Inspector Ananya Rao", email="io@nyaya.local", role="INVESTIGATING_OFFICER", clearance_level=3, demo_password=hash_demo_password(password))
        fsl_user = User(id="22222222-2222-4222-8222-222222222222", external_identity_id="22222222-2222-4222-8222-222222222222", organization_id=fsl.id, name="Dr. Vivek Shah", email="fsl@nyaya.local", role="FSL_OFFICER", clearance_level=3, demo_password=hash_demo_password(password))
        expert = User(id="33333333-3333-4333-8333-333333333333", external_identity_id="33333333-3333-4333-8333-333333333333", organization_id=fsl.id, name="External Evidence Expert", email="expert@nyaya.local", role="EXTERNAL_EXPERT", clearance_level=3, demo_password=hash_demo_password(password))
        auditor = User(id="44444444-4444-4444-8444-444444444444", external_identity_id="44444444-4444-4444-8444-444444444444", organization_id=police.id, name="Audit Officer", email="auditor@nyaya.local", role="AUDITOR", clearance_level=3, demo_password=hash_demo_password(password))
        db.add_all([io, fsl_user, expert, auditor]); db.flush()
        case = Case(case_number="MH-PUNE-2026-00142", title="Blue Swift vehicle theft and resale network", description="Synthetic SIH demonstration case. The system does not determine guilt.", case_type="Vehicle Theft", status="INVESTIGATION_ACTIVE", jurisdiction="Pune, Maharashtra", classification_level=2, fir_number="FIR-2026-PSH-881", police_station="Hadapsar Police Station", investigating_officer_id=io.id, incident_time=datetime(2026, 8, 14, 21, 20), incident_location="Gate 3, Magarpatta Road", next_hearing_at=datetime(2026, 9, 18, 10, 30))
        db.add(case); db.flush()
        db.add_all([
            CaseAssignment(case_id=case.id, user_id=io.id, assignment_role="LEAD_INVESTIGATOR"),
            CaseAssignment(case_id=case.id, user_id=fsl_user.id, assignment_role="FORENSIC_ANALYST"),
            CaseAssignment(case_id=case.id, user_id=expert.id, assignment_role="EXTERNAL_REVIEWER"),
        ])
        e12 = Evidence(case_id=case.id, evidence_code="E-12", evidence_type="Mobile Device", description="Seized mobile handset with custody gap used for demo.", classification_level=2, capture_time=datetime(2026, 8, 15, 10, 42), capture_location="Pune Police evidence room", current_custodian_org_id=fsl.id, status="ANALYSIS_PENDING")
        db.add(e12); db.flush()
        evidence_descriptions = {
            1: ("Vehicle Photograph", "Blue Swift exterior photograph"),
            2: ("CCTV Export", "Gate 3 CCTV export"),
            3: ("Witness Record", "Witness-01 signed statement"),
            4: ("Witness Record", "Witness-02 signed statement"),
            5: ("Witness Record", "Restricted Witness-03 signed statement"),
            6: ("Seizure Memo", "Vehicle-parts seizure memo"),
            8: ("Photograph", "Recovered number plate photograph"),
            9: ("Call Detail Record", "Authorized call-detail analysis extract"),
            10: ("Forensic Sample", "Residue swab sample"),
            11: ("Device Export", "Mobile extraction logical image"),
            13: ("CCTV Export", "Access-road CCTV export"),
            14: ("Court Filing", "Charge-sheet filing package"),
            15: ("Court Order", "Synthetic remand order"),
            16: ("Vehicle Record", "Registration lookup extract"),
            17: ("Location Record", "Gate 3 scene sketch"),
            18: ("Audit Export", "Evidence inventory manifest"),
            19: ("Forensic Note", "Laboratory intake verification note"),
        }
        db.add_all([
            Evidence(case_id=case.id, evidence_code=f"E-{number:02d}", evidence_type=evidence_type,
                     description=description, classification_level=3 if number == 5 else 2,
                     capture_time=datetime(2026, 8, 15, 11, min(number, 59)),
                     capture_location="Pune Police evidence room", current_custodian_org_id=police.id,
                     status="VERIFIED")
            for number, (evidence_type, description) in evidence_descriptions.items()
        ])
        source = b"NYAYAGRAPH SYNTHETIC FORENSIC REPORT\nBlue Swift residue analysis. Exhibit E-07 referenced but unavailable.\n"
        crypto = EncryptionService(); encrypted, wrapped_dek = crypto.encrypt(source)
        storage = get_storage_provider()
        forensic_reference = storage.store(f"{case.id}/seed/forensic-report-v1.bin", encrypted, "application/octet-stream")
        document = Document(case_id=case.id, evidence_id=e12.id, document_type="FORENSIC_REPORT", title="FSL residue analysis report", classification_level=2, storage_policy="PRIVATE_VAULT", created_by=fsl_user.id)
        db.add(document); db.flush()
        version = DocumentVersion(document_id=document.id, version_number=1, sha256_original=crypto.sha256_bytes(source), sha256_encrypted=crypto.sha256_bytes(encrypted), storage_reference=forensic_reference, wrapped_dek=wrapped_dek, mime_type="text/plain", size_bytes=len(source), created_by=fsl_user.id, change_reason="Synthetic demo evidence")
        db.add(version); db.flush(); document.current_version_id = version.id
        SignatureService().sign_version(db, version, fsl_user.id)
        version.fabric_tx_id = get_ledger().register_document(
            db, document_version_id=version.id, case_id=case.id, hash_value=version.sha256_original,
            actor_id=fsl_user.id, version=1, organization_id=fsl_user.organization_id,
        )
        forensic_text = source.decode()
        db.add(DocumentChunk(document_version_id=version.id, case_id=case.id, page_number=1, chunk_index=0,
                             text=forensic_text, classification_level=2, allowed_roles=[], source_hash=version.sha256_original))
        for title, doc_type, level, document_text in DEMO_DOCUMENTS:
            item = Document(case_id=case.id, document_type=doc_type, title=title, classification_level=level, storage_policy="PRIVATE_VAULT", created_by=io.id)
            db.add(item); db.flush()
            text = document_text.encode()
            encrypted_text, wk = crypto.encrypt(text)
            item_reference = storage.store(f"{case.id}/seed/{item.id}-v1.bin", encrypted_text, "application/octet-stream")
            item_version = DocumentVersion(document_id=item.id, version_number=1, sha256_original=crypto.sha256_bytes(text), sha256_encrypted=crypto.sha256_bytes(encrypted_text), storage_reference=item_reference, wrapped_dek=wk, mime_type="text/plain", size_bytes=len(text), created_by=io.id, change_reason="Synthetic seed")
            db.add(item_version); db.flush(); item.current_version_id = item_version.id
            SignatureService().sign_version(db, item_version, io.id)
            item_version.fabric_tx_id = get_ledger().register_document(
                db, document_version_id=item_version.id, case_id=case.id, hash_value=item_version.sha256_original,
                actor_id=io.id, version=1, organization_id=io.organization_id,
            )
            db.add(DocumentChunk(document_version_id=item_version.id, case_id=case.id, page_number=1, chunk_index=0,
                                 text=document_text, classification_level=level, allowed_roles=[], source_hash=item_version.sha256_original))
        for permitted_document in db.query(Document).filter(Document.case_id == case.id, Document.classification_level <= 2):
            db.add(AccessGrant(resource_type="DOCUMENT", resource_id=permitted_document.id, subject_user_id=expert.id,
                               permissions="READ", valid_from=utc_now(), expires_at=utc_now() + timedelta(days=7),
                               granted_by=io.id, reason="Seeded restricted external-review scope"))
        captured = EvidenceCustodyEvent(evidence_id=e12.id, event_type="CAPTURED", actor_user_id=io.id,
                                        purpose="Seized under memo", event_time=datetime(2026, 8, 15, 10, 42),
                                        event_hash=digest("E12-captured"))
        transferred = EvidenceCustodyEvent(evidence_id=e12.id, event_type="TRANSFERRED", from_org_id=police.id,
                                           to_org_id=fsl.id, actor_user_id=io.id,
                                           purpose="Forensic analysis after 3h22m unassigned interval",
                                           event_time=datetime(2026, 8, 15, 14, 4),
                                           previous_event_hash=captured.event_hash, event_hash=digest("E12-transfer"))
        db.add_all([captured, transferred]); db.flush()
        # Registration is the ledger provenance for initial capture. A custody
        # transfer is reserved for a real change between distinct organizations.
        captured.fabric_tx_id = get_ledger().register_evidence(
            db, evidence_id=e12.id, case_id=case.id,
            hash_value=digest(e12.evidence_code), actor_id=io.id,
            organization_id=io.organization_id,
        )
        transferred.fabric_tx_id = get_ledger().transfer_custody(
            db, evidence_id=e12.id, event_hash=transferred.event_hash, actor_id=io.id,
            case_id=case.id, previous_hash=transferred.previous_event_hash,
            from_org=police.id, to_org=fsl.id,
        )
        db.commit()
        print(f"Seeded case {case.case_number}; forensic version {version.id}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--reset", action="store_true")
    run(parser.parse_args().reset)
