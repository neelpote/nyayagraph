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

MOCK_CASES = [
    ("MH-MUM-2026-00201", "Phishing payment trail", "Cyber Fraud", "INVESTIGATION_ACTIVE", "Mumbai, Maharashtra", "Cyber Police Station", "FIR-2026-MUM-201", "Email export", "DIGITAL_EVIDENCE", "A fictional phishing email and payment-reference export prepared for system testing."),
    ("MH-NAG-2026-00202", "Warehouse narcotics seizure", "Narcotics", "FORENSIC_REVIEW", "Nagpur, Maharashtra", "Sadar Police Station", "FIR-2026-NAG-202", "Seizure inventory", "SEIZURE_MEMO", "A fictional sealed-property inventory awaiting laboratory review."),
    ("MH-NAS-2026-00203", "Jewellery shop burglary", "Burglary", "INVESTIGATION_ACTIVE", "Nashik, Maharashtra", "Sarkarwada Police Station", "FIR-2026-NAS-203", "Scene inspection note", "SCENE_REPORT", "A fictional scene note recording entry-point and property observations."),
    ("MH-AUR-2026-00204", "Missing student inquiry", "Missing Person", "INVESTIGATION_ACTIVE", "Chhatrapati Sambhajinagar, Maharashtra", "City Chowk Police Station", "FIR-2026-AUR-204", "Last-seen statement", "WITNESS_STATEMENT", "A fictional witness statement created without using any real person's information."),
    ("MH-KOL-2026-00205", "Counterfeit licence inquiry", "Document Fraud", "CHARGE_SHEET_FILED", "Kolhapur, Maharashtra", "Shahupuri Police Station", "FIR-2026-KOL-205", "Document examination", "FORENSIC_REPORT", "A fictional comparison of security features in a questioned driving licence."),
    ("MH-THA-2026-00206", "Unlicensed arms recovery", "Arms Act", "FORENSIC_REVIEW", "Thane, Maharashtra", "Wagle Estate Police Station", "FIR-2026-THA-206", "Ballistics intake note", "FORENSIC_REPORT", "A fictional laboratory intake record for a sealed recovered object."),
    ("MH-PUN-2026-00207", "Invoice diversion fraud", "Financial Fraud", "INVESTIGATION_ACTIVE", "Pune, Maharashtra", "Shivajinagar Police Station", "FIR-2026-PUN-207", "Transaction analysis", "FINANCIAL_ANALYSIS", "A fictional transaction summary used to test evidence-grounded financial review."),
    ("MH-SOL-2026-00208", "Market assault investigation", "Assault", "COURT_REVIEW", "Solapur, Maharashtra", "Foujdar Chawdi Police Station", "FIR-2026-SOL-208", "Medical evidence index", "EVIDENCE_INDEX", "A fictional index of authorized medical and scene records; it contains no real health data."),
    ("MH-SAT-2026-00209", "Recovered vehicle parts network", "Vehicle Theft", "INVESTIGATION_ACTIVE", "Satara, Maharashtra", "Satara City Police Station", "FIR-2026-SAT-209", "Vehicle-parts inventory", "SEIZURE_MEMO", "A fictional inventory linking recovered vehicle parts for provenance testing."),
    ("MH-AMR-2026-00210", "Messaging extortion complaint", "Cyber Extortion", "INVESTIGATION_ACTIVE", "Amravati, Maharashtra", "Cyber Police Station", "FIR-2026-AMR-210", "Message export manifest", "DIGITAL_EVIDENCE", "A fictional, sanitized message-export manifest with no real account identifiers."),
    ("MH-SAN-2026-00211", "Agricultural warehouse theft", "Theft", "CHARGE_SHEET_FILED", "Sangli, Maharashtra", "Vishrambag Police Station", "FIR-2026-SAN-211", "Warehouse CCTV digest", "CCTV_REPORT", "A fictional CCTV observation digest for a warehouse access event."),
    ("MH-AHM-2026-00212", "Identity document misuse", "Identity Theft", "FORENSIC_REVIEW", "Ahmednagar, Maharashtra", "Kotwali Police Station", "FIR-2026-AHM-212", "Identity comparison note", "FORENSIC_REPORT", "A fictional identity-document comparison containing no real identity data."),
    ("MH-RAT-2026-00213", "Coastal recruitment inquiry", "Organized Crime", "INVESTIGATION_ACTIVE", "Ratnagiri, Maharashtra", "Ratnagiri City Police Station", "FIR-2026-RAT-213", "Interview record index", "EVIDENCE_INDEX", "A fictional and non-identifying index of interview records for workflow testing."),
    ("MH-JAL-2026-00214", "Illegal firearm supply inquiry", "Arms Act", "COURT_REVIEW", "Jalgaon, Maharashtra", "Zilla Peth Police Station", "FIR-2026-JAL-214", "Custody submission note", "CUSTODY_RECORD", "A fictional court-submission custody note for a sealed evidence package."),
    ("MH-LAT-2026-00215", "Commercial premises arson", "Arson", "FORENSIC_REVIEW", "Latur, Maharashtra", "Gandhi Chowk Police Station", "FIR-2026-LAT-215", "Fire-scene sample report", "FORENSIC_REPORT", "A fictional fire-scene sample report awaiting investigator interpretation."),
    ("MH-AKO-2026-00216", "Mobile handset theft ring", "Organized Theft", "INVESTIGATION_ACTIVE", "Akola, Maharashtra", "Civil Lines Police Station", "FIR-2026-AKO-216", "Recovered device inventory", "SEIZURE_MEMO", "A fictional inventory of recovered test devices with synthetic identifiers."),
    ("MH-PAL-2026-00217", "Court filing compliance review", "Court Compliance", "CLOSED", "Palghar, Maharashtra", "Palghar Police Station", "FIR-2026-PAL-217", "Closure verification note", "COURT_ORDER", "A fictional closure-verification record used to exercise completed-case views."),
]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def seed_additional_mock_cases(db, police, fsl, io, fsl_user, crypto, storage) -> int:
    """Add compact fictional cases while exercising the real secure ingestion path."""
    created = 0
    for index, (case_number, title, case_type, status, jurisdiction, station, fir_number,
                document_title, document_type, document_text) in enumerate(MOCK_CASES, start=1):
        if db.query(Case).filter_by(case_number=case_number).first():
            continue
        classification = 3 if index % 4 == 0 else 2
        incident_time = datetime(2026, 5, 1, 9, 0) + timedelta(days=index * 4, minutes=index * 11)
        mock_case = Case(
            case_number=case_number,
            title=title,
            description="Fictional NyayaGraph mock case for authorized product testing. No real person, victim, witness, or government record is represented.",
            case_type=case_type,
            status=status,
            jurisdiction=jurisdiction,
            classification_level=classification,
            fir_number=fir_number,
            police_station=station,
            investigating_officer_id=io.id,
            incident_time=incident_time,
            incident_location=f"Synthetic test location, {jurisdiction}",
            next_hearing_at=None if status == "CLOSED" else incident_time + timedelta(days=45),
        )
        db.add(mock_case); db.flush()
        assignments = [CaseAssignment(case_id=mock_case.id, user_id=io.id, assignment_role="LEAD_INVESTIGATOR")]
        if document_type == "FORENSIC_REPORT":
            assignments.append(CaseAssignment(case_id=mock_case.id, user_id=fsl_user.id, assignment_role="FORENSIC_ANALYST"))
        db.add_all(assignments)

        evidence = Evidence(
            case_id=mock_case.id,
            evidence_code=f"MOCK-E-{index:02d}",
            evidence_type=document_type.replace("_", " ").title(),
            description=f"Fictional evidence item for {title.lower()}.",
            classification_level=classification,
            capture_time=incident_time + timedelta(hours=2),
            capture_location=f"Mock evidence desk, {jurisdiction}",
            current_custodian_org_id=fsl.id if document_type == "FORENSIC_REPORT" else police.id,
            status="VERIFIED",
        )
        db.add(evidence); db.flush()

        artifact_text = (
            "NYAYAGRAPH FICTIONAL MOCK RECORD\n"
            f"Case: {case_number}\n"
            f"Title: {document_title}\n"
            f"Summary: {document_text}\n"
            "This record is synthetic and must not be represented as government data.\n"
        )
        plaintext = artifact_text.encode()
        encrypted, wrapped_dek = crypto.encrypt(plaintext)
        document = Document(
            case_id=mock_case.id,
            evidence_id=evidence.id,
            document_type=document_type,
            title=f"{document_title} — MOCK",
            classification_level=classification,
            storage_policy="PRIVATE_VAULT",
            created_by=io.id,
        )
        db.add(document); db.flush()
        storage_reference = storage.store(
            f"{mock_case.id}/seed/{document.id}-v1.bin", encrypted, "application/octet-stream"
        )
        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            sha256_original=crypto.sha256_bytes(plaintext),
            sha256_encrypted=crypto.sha256_bytes(encrypted),
            storage_reference=storage_reference,
            wrapped_dek=wrapped_dek,
            mime_type="text/plain",
            size_bytes=len(plaintext),
            created_by=io.id,
            change_reason="Fictional mock dataset seed",
        )
        db.add(version); db.flush(); document.current_version_id = version.id
        SignatureService().sign_version(db, version, io.id)
        version.fabric_tx_id = get_ledger().register_document(
            db, document_version_id=version.id, case_id=mock_case.id,
            hash_value=version.sha256_original, actor_id=io.id, version=1,
            organization_id=io.organization_id,
        )
        db.add(DocumentChunk(
            document_version_id=version.id,
            case_id=mock_case.id,
            page_number=1,
            chunk_index=0,
            text=artifact_text,
            classification_level=classification,
            allowed_roles=[],
            source_hash=version.sha256_original,
        ))
        created += 1
    return created


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
        existing_flagship = db.query(Case).filter_by(case_number="MH-PUNE-2026-00142").first()
        if existing_flagship:
            police = db.query(Organization).filter_by(fabric_msp_id="PoliceMSP").one()
            fsl = db.query(Organization).filter_by(fabric_msp_id="FSLMSP").one()
            io = db.query(User).filter_by(email="io@nyaya.local").one()
            fsl_user = db.query(User).filter_by(email="fsl@nyaya.local").one()
            created = seed_additional_mock_cases(
                db, police, fsl, io, fsl_user, EncryptionService(), get_storage_provider()
            )
            db.commit()
            print(f"Seed dataset ready: {db.query(Case).count()} fictional cases ({created} added)")
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
        additional_count = seed_additional_mock_cases(db, police, fsl, io, fsl_user, crypto, storage)
        db.commit()
        print(f"Seeded {additional_count + 1} fictional cases; flagship forensic version {version.id}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--reset", action="store_true")
    run(parser.parse_args().reset)
