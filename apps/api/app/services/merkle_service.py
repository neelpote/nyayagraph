from __future__ import annotations

import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..blockchain.ledger import get_ledger
from ..blockchain.public_anchor import get_public_anchor_provider
from ..models import AuditEvent, BlockchainAnchor, Case, MerkleBatch, MerkleLeaf
from ..security.auth import AuthenticatedUser
from ..security.policy import policy_engine


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_pair(left: str, right: str) -> str:
    return sha256_hex(bytes.fromhex(left) + bytes.fromhex(right))


def build_levels(leaves: list[str]) -> list[list[str]]:
    if not leaves:
        raise ValueError("At least one leaf is required")
    levels = [leaves]
    while len(levels[-1]) > 1:
        current = levels[-1]
        next_level = [hash_pair(current[index], current[index + 1] if index + 1 < len(current) else current[index])
                      for index in range(0, len(current), 2)]
        levels.append(next_level)
    return levels


def proof_for(leaves: list[str], leaf_index: int) -> list[dict]:
    siblings: list[dict] = []
    index = leaf_index
    for level in build_levels(leaves)[:-1]:
        sibling_index = index - 1 if index % 2 else index + 1
        if sibling_index >= len(level):
            sibling_index = index
        siblings.append({"hash": level[sibling_index], "position": "LEFT" if sibling_index < index else "RIGHT"})
        index //= 2
    return siblings


def verify_proof(leaf: str, siblings: list[dict], root: str) -> bool:
    current = leaf
    for sibling in siblings:
        current = hash_pair(sibling["hash"], current) if sibling["position"] == "LEFT" else hash_pair(current, sibling["hash"])
    return current == root


class MerkleCheckpointService:
    def canonicalize(self, event: AuditEvent) -> bytes:
        value = {
            "action": event.action,
            "authorization_decision": event.authorization_decision,
            "created_at": event.created_at.isoformat(timespec="microseconds"),
            "event_id": event.id,
            "resource_id": event.resource_id,
            "resource_type": event.resource_type,
            "schema_version": "1",
        }
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()

    def create_checkpoint(self, db: Session, actor_id: str, limit: int = 10) -> dict:
        already_batched = select(MerkleLeaf.event_id)
        events = list(db.scalars(select(AuditEvent).where(AuditEvent.id.not_in(already_batched)).order_by(AuditEvent.created_at, AuditEvent.id).limit(limit)))
        if not events:
            raise HTTPException(status_code=409, detail="No eligible provenance events")
        leaves = [sha256_hex(self.canonicalize(event)) for event in events]
        root = build_levels(leaves)[-1][0]
        batch_number = (db.scalar(select(func.max(MerkleBatch.batch_number))) or 0) + 1
        metadata_commitment = sha256_hex(json.dumps({"event_count": len(events), "schema_version": "1"}, sort_keys=True).encode())
        batch = MerkleBatch(batch_number=batch_number, merkle_root=root, event_count=len(events), anchor_status="PENDING")
        db.add(batch); db.flush()
        # The human-facing sequence can restart after a development reset. The
        # contract key cannot, so derive a stable non-sensitive uint256 identifier
        # from the database UUID rather than reusing the display sequence.
        public_batch_id = int(sha256_hex(batch.id.encode()), 16)
        for index, (event, leaf) in enumerate(zip(events, leaves)):
            db.add(MerkleLeaf(batch_id=batch.id, event_type=event.action, event_id=event.id, leaf_hash=leaf, leaf_index=index))
        fabric_tx_id = get_ledger().record_checkpoint(
            db, batch_id=batch.id, root=root, metadata_commitment=metadata_commitment, actor_id=actor_id
        )
        # Persist the private provenance record first. If an external network is
        # unavailable, the checkpoint remains valid and visibly pending.
        db.commit()
        anchor_result = get_public_anchor_provider().anchor_root(
            root=root, batch_number=public_batch_id, metadata_commitment=metadata_commitment
        )
        batch.public_tx_hash = anchor_result["transaction_hash"]
        batch.public_chain_id = anchor_result["chain_id"]
        batch.anchor_status = anchor_result["status"]
        db.add(BlockchainAnchor(batch_id=batch.id, chain_type=anchor_result["chain_type"], chain_id=anchor_result["chain_id"],
                                contract_address=anchor_result["contract_address"], transaction_hash=anchor_result["transaction_hash"],
                                block_number=anchor_result["block_number"]))
        db.commit()
        return {"batchId": batch.id, "batchNumber": batch.batch_number, "merkleRoot": root, "eventCount": len(events),
                "anchorStatus": batch.anchor_status, "fabricTransaction": fabric_tx_id,
                "publicTransaction": batch.public_tx_hash, "chainId": batch.public_chain_id}

    def proof(self, db: Session, actor: AuthenticatedUser, event_id: str) -> dict:
        leaf = db.scalar(select(MerkleLeaf).where(MerkleLeaf.event_id == event_id))
        if not leaf:
            raise HTTPException(status_code=404, detail="Merkle proof not found")
        event = db.get(AuditEvent, event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Merkle proof not found")
        if event.case_id:
            case = db.get(Case, event.case_id)
            if not case or not policy_engine.can_view_case(db, actor, case):
                raise HTTPException(status_code=404, detail="Merkle proof not found")
        elif actor.role not in {"ADMIN", "AUDITOR"}:
            raise HTTPException(status_code=403, detail="Operational proof access denied")
        batch = db.get(MerkleBatch, leaf.batch_id)
        ordered = list(db.scalars(select(MerkleLeaf).where(MerkleLeaf.batch_id == leaf.batch_id).order_by(MerkleLeaf.leaf_index)))
        siblings = proof_for([item.leaf_hash for item in ordered], leaf.leaf_index)
        return {"leaf": leaf.leaf_hash, "root": batch.merkle_root, "siblings": siblings, "leafIndex": leaf.leaf_index,
                "batchId": batch.id, "batchNumber": batch.batch_number, "publicTransaction": batch.public_tx_hash,
                "anchorStatus": batch.anchor_status, "verified": verify_proof(leaf.leaf_hash, siblings, batch.merkle_root)}
