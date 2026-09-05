from __future__ import annotations

import argparse
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..blockchain.ledger import FabricProvenanceLedger, LedgerUnavailableError
from ..database import SessionLocal
from ..models import AccessGrant, DocumentVersion, EvidenceCustodyEvent, OutboxEvent
from ..utils.time import utc_now


class OutboxService:
    """Retry committed provider work with row locking and bounded backoff."""

    def process(self, db: Session, limit: int = 50) -> dict[str, int]:
        now = utc_now()
        events = list(db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.status.in_(["PENDING", "RETRY"]), OutboxEvent.available_at <= now)
            .order_by(OutboxEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ))
        completed = failed = 0
        ledger = FabricProvenanceLedger()
        for event in events:
            operation = event.topic.removeprefix("fabric.")
            try:
                transaction_id = getattr(ledger, operation)(db, **event.payload_json)
                self._record_transaction(db, operation, event.payload_json, transaction_id)
                event.status = "COMPLETED"
                event.processed_at = now
                event.last_error = None
                completed += 1
            except (LedgerUnavailableError, AttributeError, TypeError, ValueError) as error:
                event.attempts += 1
                event.status = "FAILED" if event.attempts >= 10 else "RETRY"
                event.available_at = now + timedelta(seconds=min(3600, 2 ** min(event.attempts, 11)))
                event.last_error = str(error)[-500:]
                failed += 1
        db.commit()
        return {"selected": len(events), "completed": completed, "failed": failed}

    @staticmethod
    def _record_transaction(db: Session, operation: str, payload: dict, transaction_id: str) -> None:
        if operation in {"register_document", "create_version"}:
            row = db.get(DocumentVersion, payload.get("document_version_id"))
        elif operation == "transfer_custody":
            row = db.get(EvidenceCustodyEvent, payload.get("event_id"))
        elif operation in {"grant_access", "revoke_access"}:
            row = db.get(AccessGrant, payload.get("grant_id"))
        else:
            row = None
        if row is not None:
            row.fabric_tx_id = transaction_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Retry NyayaGraph provider outbox events")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    with SessionLocal() as db:
        print(OutboxService().process(db, max(1, min(args.limit, 500))))


if __name__ == "__main__":
    main()
