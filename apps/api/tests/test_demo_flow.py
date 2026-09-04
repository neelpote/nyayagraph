import base64
import os
import fitz

os.environ["DATABASE_URL"] = "sqlite:///./data/test-demo.db"
os.environ["MASTER_KEK_BASE64"] = base64.b64encode(b"b" * 32).decode()
os.environ["DEMO_PASSWORD"] = "NyayaDemo!2026"

from fastapi.testclient import TestClient
from app.main import app
from app.seed import run as seed
from app.database import SessionLocal
from app.models import Case, Document, DocumentVersion, Evidence


def login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/dev-login", json={"email": email, "password": "NyayaDemo!2026"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_role_filter_and_tamper_verification():
    seed(reset=True)
    client = TestClient(app)
    io_headers = login(client, "io@nyaya.local")
    fsl_headers = login(client, "fsl@nyaya.local")
    expert_headers = login(client, "expert@nyaya.local")

    io_case = client.get("/api/v1/cases/MH-PUNE-2026-00142", headers=io_headers)
    expert_case = client.get("/api/v1/cases/MH-PUNE-2026-00142", headers=expert_headers)
    assert io_case.status_code == expert_case.status_code == 200
    assert any(item["title"] == "Witness-03 statement — restricted" for item in io_case.json()["documents"])
    assert all(item["title"] != "Witness-03 statement — restricted" for item in expert_case.json()["documents"])
    assert len(expert_case.json()["documents"]) > 0
    expert_timeline = client.get("/api/v1/cases/MH-PUNE-2026-00142/timeline", headers=expert_headers)
    assert expert_timeline.status_code == 200
    assert all("Witness-03" not in item["title"] for item in expert_timeline.json())

    restricted = next(item for item in io_case.json()["documents"] if item["title"] == "Witness-03 statement — restricted")
    restricted_ai = client.post(
        "/api/v1/ai/case/MH-PUNE-2026-00142/ask", headers=expert_headers,
        json={"question": "What did Witness-03 report?"},
    )
    assert restricted_ai.status_code == 200
    assert restricted_ai.json()["status"] == "INSUFFICIENT_EVIDENCE"
    assert restricted_ai.json()["sources"] == []
    assert client.get(f"/api/v1/documents/{restricted['id']}/download", headers=expert_headers).status_code == 403
    assert client.post("/api/v1/access/break-glass", headers=expert_headers, json={
        "document_id": restricted["id"], "justification": "Emergency review attempt without an authorized role",
        "requested_scope": "Restricted witness statement", "minutes": 30,
    }).status_code == 403

    malformed = client.post(
        "/api/v1/documents", headers=io_headers,
        data={"case_id": io_case.json()["id"], "title": "Malformed PDF", "document_type": "OTHER", "classification_level": "2"},
        files={"file": ("malformed.pdf", b"%PDF-1.4\nnot a real PDF\n%%EOF", "application/pdf")},
    )
    assert malformed.status_code == 422

    created = client.post("/api/v1/cases", headers=io_headers, json={
        "case_number": "MH-PUNE-2026-00999", "title": "Synthetic authorization boundary case",
        "description": "A second synthetic case used to prove assignment isolation.",
        "case_type": "Vehicle Theft", "jurisdiction": "Pune, Maharashtra",
        "fir_number": "FIR-2026-PSH-999", "police_station": "Hadapsar Police Station",
        "classification_level": 2,
    })
    assert created.status_code == 200
    assert client.get("/api/v1/cases/MH-PUNE-2026-00999", headers=io_headers).status_code == 200
    assert client.get("/api/v1/cases/MH-PUNE-2026-00999", headers=expert_headers).status_code == 403
    cross_case_upload = client.post(
        "/api/v1/documents", headers=fsl_headers,
        data={"case_id": created.json()["id"], "title": "Unauthorized target", "document_type": "OTHER", "classification_level": "2"},
        files={"file": ("record.txt", b"authorized format but unauthorized case", "text/plain")},
    )
    assert cross_case_upload.status_code == 403
    with SessionLocal() as db:
        other_evidence = Evidence(case_id=created.json()["id"], evidence_code="OTHER-01", evidence_type="TEST",
                                  description="Authorization-boundary record", classification_level=2, status="REGISTERED")
        db.add(other_evidence); db.commit(); evidence_id = other_evidence.id
    assert client.get(f"/api/v1/evidence/{evidence_id}/passport", headers=expert_headers).status_code == 404

    forensic = next(item for item in io_case.json()["documents"] if item["title"] == "FSL residue analysis report")
    response = client.post(
        "/api/v1/verification/document",
        headers=io_headers,
        data={"document_version_id": forensic["versionId"]},
        files={"file": ("forensic-modified.pdf", b"modified evidence", "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "HASH_MISMATCH"


def test_expert_cannot_verify_restricted_document():
    seed(reset=True)
    client = TestClient(app)
    io_headers = login(client, "io@nyaya.local")
    expert_headers = login(client, "expert@nyaya.local")
    io_case = client.get("/api/v1/cases/MH-PUNE-2026-00142", headers=io_headers).json()
    restricted = next(item for item in io_case["documents"] if item["title"] == "Witness-03 statement — restricted")

    response = client.post(
        "/api/v1/verification/document",
        headers=expert_headers,
        data={"document_version_id": restricted["versionId"]},
        files={"file": ("statement.txt", b"probe", "text/plain")},
    )
    assert response.status_code == 403


def test_new_document_version_links_to_previous_hash():
    seed(reset=True)
    client = TestClient(app)
    io_headers = login(client, "io@nyaya.local")
    case = client.get("/api/v1/cases/MH-PUNE-2026-00142", headers=io_headers).json()
    forensic = next(item for item in case["documents"] if item["title"] == "FSL residue analysis report")

    corrected = fitz.open()
    page = corrected.new_page()
    page.insert_text((72, 72), "Corrected synthetic forensic report")
    corrected_pdf = corrected.tobytes()
    corrected.close()
    response = client.post(
        f"/api/v1/documents/{forensic['id']}/versions",
        headers=io_headers,
        data={"change_reason": "Corrected laboratory reference"},
        files={"file": ("forensic-v2.pdf", corrected_pdf, "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["versionNumber"] == 2
    assert body["previousVersionHash"]
    assert body["previousVersionHash"] != body["sha256Original"]


def test_verification_upload_rejects_body_over_shared_limit():
    seed(reset=True)
    client = TestClient(app)
    headers = login(client, "io@nyaya.local")
    case = client.get("/api/v1/cases/MH-PUNE-2026-00142", headers=headers).json()
    version_id = case["documents"][0]["versionId"]
    response = client.post(
        "/api/v1/verification/document",
        headers=headers,
        data={"document_version_id": version_id},
        files={"file": ("oversized.bin", b"x" * (20 * 1024 * 1024 + 1), "application/octet-stream")},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "File is empty or exceeds upload limit"


def test_all_18_fictional_cases_have_verified_real_artifacts():
    seed(reset=True)
    client = TestClient(app)
    headers = login(client, "io@nyaya.local")

    case_list = client.get("/api/v1/cases", headers=headers)
    assert case_list.status_code == 200
    cases = case_list.json()
    assert len(cases) == 18
    assert len({item["caseNumber"] for item in cases}) == 18
    assert len({item["type"] for item in cases}) >= 10
    assert len({item["status"] for item in cases}) >= 5

    for item in cases:
        workspace = client.get(f"/api/v1/cases/{item['caseNumber']}", headers=headers)
        assert workspace.status_code == 200
        body = workspace.json()
        assert body["documents"], item["caseNumber"]
        assert body["evidence"], item["caseNumber"]
        assert body["integrity"]["documents"]["verified"] == body["integrity"]["documents"]["total"]
        assert body["integrity"]["signatures"]["valid"] == body["integrity"]["signatures"]["total"]

    with SessionLocal() as db:
        mock_cases = db.query(Case).filter(Case.case_number != "MH-PUNE-2026-00142").all()
        assert len(mock_cases) == 17
        for mock_case in mock_cases:
            assert mock_case.description.startswith("Fictional NyayaGraph mock case")
            document = db.query(Document).filter_by(case_id=mock_case.id).one()
            version = db.get(DocumentVersion, document.current_version_id)
            assert document.title.endswith("— MOCK")
            assert version is not None
            assert len(version.sha256_original) == 64
            assert len(version.sha256_encrypted) == 64
            assert version.fabric_tx_id
