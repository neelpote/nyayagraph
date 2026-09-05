from __future__ import annotations

import logging

from sqlalchemy import event
from sqlalchemy.orm import Session

from .providers import storage_provider_for_reference

_PENDING_STORAGE_WRITES = "nyayagraph_pending_storage_writes"
logger = logging.getLogger("nyayagraph.storage")


def track_storage_write(db: Session, reference: str) -> None:
    """Delete a newly written object if its owning SQL transaction rolls back."""
    db.info.setdefault(_PENDING_STORAGE_WRITES, []).append(reference)


@event.listens_for(Session, "after_commit")
def _clear_committed_storage_writes(db: Session) -> None:
    db.info.pop(_PENDING_STORAGE_WRITES, None)


@event.listens_for(Session, "after_rollback")
def _remove_orphaned_storage_writes(db: Session) -> None:
    for reference in db.info.pop(_PENDING_STORAGE_WRITES, []):
        try:
            storage_provider_for_reference(reference).delete(reference)
        except Exception:
            # Rollback must remain reliable even when the provider is unavailable.
            # Object-store lifecycle/orphan reconciliation is the final safety net.
            logger.exception(
                "Failed to remove rolled-back encrypted object",
                extra={"storage_backend": reference.partition("://")[0]},
            )
