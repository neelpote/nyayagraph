from __future__ import annotations

from typing import Protocol


class JusticeSystemAdapter(Protocol):
    def fetch_case(self, case_number: str) -> dict: ...
    def fetch_documents(self, case_number: str) -> list[dict]: ...
    def fetch_evidence_metadata(self, case_number: str) -> list[dict]: ...
    def fetch_status(self) -> dict: ...


class SimulatedJusticeAdapter:
    """Interface demonstrator only; it never claims a government connection."""

    def __init__(self, adapter_id: str, name: str) -> None:
        self.adapter_id = adapter_id
        self.name = name

    def fetch_case(self, case_number: str) -> dict:
        return {"caseNumber": case_number, "mode": "SIMULATED", "records": []}

    def fetch_documents(self, case_number: str) -> list[dict]:
        return []

    def fetch_evidence_metadata(self, case_number: str) -> list[dict]:
        return []

    def fetch_status(self) -> dict:
        return {"id": self.adapter_id, "name": self.name, "status": "SIMULATED",
                "lastSync": None, "recordsImported": 0, "authenticationMode": "Demo adapter",
                "simulated": True}


def configured_adapters() -> list[SimulatedJusticeAdapter]:
    return [SimulatedJusticeAdapter(adapter_id, name) for adapter_id, name in (
        ("cctns", "CCTNS"), ("esakshya", "eSakshya"), ("icjs", "ICJS"),
        ("ecourts", "eCourts"), ("eforensics", "eForensics"),
        ("eprosecution", "eProsecution"), ("eprisons", "ePrisons"),
    )]
