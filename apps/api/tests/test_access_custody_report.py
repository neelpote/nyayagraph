import base64
import os
import re
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite:///./data/test-trust-workflows.db"
os.environ["MASTER_KEK_BASE64"] = base64.b64encode(b"c" * 32).decode()
os.environ["DEMO_PASSWORD"] = "NyayaDemo!2026"

from fastapi.testclient import TestClient
from app.database import SessionLocal
from app.main import app
from app.models import DocumentVersion, Organization, Signature, User
from app.security.signatures import SignatureService
from app.seed import run as seed


def auth(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/dev-login", json={"email": email, "password": "NyayaDemo!2026"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_temporary_grant_reveals_only_granted_restricted_document():
    seed(reset=True)
    client = TestClient(app)
    io_headers = auth(client, "io@nyaya.local")
    expert_headers = auth(client, "expert@nyaya.local")
    io_case = client.get("/api/v1/cases/MH-PUNE-2026-00142", headers=io_headers).json()
    restricted = next(item for item in io_case["documents"] if "Witness-03" in item["title"])
    before = client.get("/api/v1/cases/MH-PUNE-2026-00142", headers=expert_headers).json()
    assert all("Witness-03" not in item["title"] for item in before["documents"])
    before_ai = client.post("/api/v1/ai/case/MH-PUNE-2026-00142/ask", headers=expert_headers,
                            json={"question": "What did Witness-03 report?"}).json()
    assert before_ai["status"] == "INSUFFICIENT_EVIDENCE"
    assert before_ai["sources"] == []

    unsupported_grant = client.post("/api/v1/access/grants", headers=io_headers, json={
        "document_id": restricted["id"], "subject_email": "expert@nyaya.local",
        "expires_at": (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2)).isoformat(),
        "reason": "Attempt to grant an unsupported permission for testing", "permissions": "WRITE",
    })
    assert unsupported_grant.status_code == 422

    grant = client.post("/api/v1/access/grants", headers=io_headers, json={
        "document_id": restricted["id"], "subject_email": "expert@nyaya.local",
        "expires_at": (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2)).isoformat(),
        "reason": "Forensic comparison for the authorized review window", "permissions": "READ",
    })
    assert grant.status_code == 200
    after = client.get("/api/v1/cases/MH-PUNE-2026-00142", headers=expert_headers).json()
    assert any("Witness-03" in item["title"] for item in after["documents"])
    after_ai = client.post("/api/v1/ai/case/MH-PUNE-2026-00142/ask", headers=expert_headers,
                           json={"question": "What did Witness-03 report?"}).json()
    assert after_ai["status"] == "SUPPORTED"
    assert any("Witness-03" in source["documentTitle"] for source in after_ai["sources"])


def test_current_custodian_can_transfer_evidence():
    seed(reset=True)
    client = TestClient(app)
    fsl_headers = auth(client, "fsl@nyaya.local")
    with SessionLocal() as db:
        police = db.query(Organization).filter_by(name="Pune Police").one()
        police_id = police.id
    response = client.post("/api/v1/evidence/E-12/custody", headers=fsl_headers, json={
        "to_org_id": police_id, "purpose": "Return following authorized forensic analysis", "location": "Pune Police evidence room",
    })
    assert response.status_code == 200
    assert response.json()["eventHash"]
    assert response.json()["previousEventHash"]


def test_report_qr_endpoint_reveals_only_authenticity_state():
    seed(reset=True)
    client = TestClient(app)
    report = client.get("/api/v1/cases/MH-PUNE-2026-00142/verification-report", headers=auth(client, "io@nyaya.local"))
    assert report.status_code == 200
    assert "Section-63-supporting metadata" in report.text
    match = re.search(r"/public/verify/([A-Za-z0-9_-]+)", report.text)
    assert match
    public = client.get(f"/api/v1/public/verify/{match.group(1)}")
    assert public.status_code == 200
    assert set(public.json()) == {"status", "hashVerified", "signatureVerified", "versionVerified", "anchorVerified"}
    assert public.json()["anchorVerified"] is False
    assert public.json()["status"] == "VERIFICATION_WARNING"


def test_report_never_claims_authenticity_after_signature_corruption():
    seed(reset=True)
    with SessionLocal() as db:
        signature = db.query(Signature).first()
        signature.signature_value = "invalid-base64-signature"
        db.commit()
    client = TestClient(app)
    report = client.get("/api/v1/cases/MH-PUNE-2026-00142/verification-report",
                        headers=auth(client, "io@nyaya.local"))
    token = re.search(r"/public/verify/([A-Za-z0-9_-]+)", report.text)
    assert token
    result = client.get(f"/api/v1/public/verify/{token.group(1)}").json()
    assert result["status"] == "VERIFICATION_WARNING"
    assert result["signatureVerified"] is False


def test_service_attestation_is_bound_to_recorded_submitting_actor():
    seed(reset=True)
    with SessionLocal() as db:
        signature = db.query(Signature).first()
        version = db.get(DocumentVersion, signature.artifact_id)
        other_user = db.query(User).filter(User.id != signature.signer_user_id).first()
        assert signature.algorithm == SignatureService.ALGORITHM
        assert SignatureService().verify_version(db, version) is True
        original_actor = signature.signer_user_id
        signature.signer_user_id = other_user.id
        db.flush()
        assert SignatureService().verify_version(db, version) is False
        signature.signer_user_id = original_actor
        signature.public_key_reference = base64.b64encode(b"x" * 32).decode()
        db.flush()
        assert SignatureService().verify_version(db, version) is False
