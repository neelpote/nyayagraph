from .blockchain.ledger import get_ledger
from .database import SessionLocal
from .models import Document, DocumentVersion, User


def run() -> int:
    """Replace development provenance references with genuine Fabric transactions."""
    synchronized = 0
    with SessionLocal() as db:
        actor = db.query(User).filter_by(email="io@nyaya.local").one()
        versions = db.query(DocumentVersion).filter(
            (DocumentVersion.fabric_tx_id.is_(None)) |
            (DocumentVersion.fabric_tx_id.like("dev-ledger-%"))
        ).all()
        ledger = get_ledger()
        for version in versions:
            document = db.get(Document, version.document_id)
            transaction_id = ledger.register_document(
                db,
                document_version_id=version.id,
                case_id=document.case_id,
                hash_value=version.sha256_original,
                actor_id=actor.id,
                version=version.version_number,
                organization_id=actor.organization_id,
            )
            if transaction_id.startswith("dev-ledger-"):
                db.rollback()
                raise RuntimeError("Fabric is unavailable; provenance remains in development ledger mode")
            version.fabric_tx_id = transaction_id
            db.commit()
            synchronized += 1
    print(f"Fabric synchronization complete: {synchronized} document versions updated")
    return synchronized


if __name__ == "__main__":
    run()
