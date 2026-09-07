from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import select
from ..ai.corpus import AuthorizedCorpus
from ..ai.case_agent import require_case
from ..models import Document, DocumentVersion, Entity, EntityRelationship, Evidence
from ..security.auth import AuthenticatedUser
from ..security.policy import policy_engine


class GraphService:
    """PostgreSQL-backed DTO fallback derived from authorized case records."""

    def __init__(self):
        self.corpus = AuthorizedCorpus()

    def case_graph(self, db: Session, actor: AuthenticatedUser, case_number: str) -> dict:
        case = require_case(db, actor, case_number)
        chunks = self.corpus.for_case(db, actor, case)
        nodes = [{"id": f"case:{case.id}", "label": case.case_number, "type": "Case"}]
        edges = []
        for chunk in chunks:
            node_id = f"document:{chunk.document_id}"
            nodes.append({"id": node_id, "label": chunk.document_title, "type": "Document"})
            edges.append({"source": node_id, "target": f"case:{case.id}", "label": "RELATED_TO"})
        authorized_document_ids = {chunk.document_id for chunk in chunks}
        for evidence in db.scalars(select(Evidence).where(Evidence.case_id == case.id)):
            if not policy_engine.can_view_evidence(db, actor, evidence):
                continue
            node_id = f"evidence:{evidence.id}"
            nodes.append({"id": node_id, "label": evidence.evidence_code, "type": "Evidence"})
            edges.append({"source": node_id, "target": f"case:{case.id}", "label": "REGISTERED_IN"})
            document = db.scalar(select(Document).where(Document.evidence_id == evidence.id))
            if document and document.id in authorized_document_ids:
                edges.append({"source": f"document:{document.id}", "target": node_id, "label": "SUPPORTED_BY"})
        entities = list(db.scalars(select(Entity).where(
            Entity.case_id == case.id,
            Entity.classification_level <= actor.clearance_level,
        )))
        visible_entity_ids = {entity.id for entity in entities}
        nodes.extend({"id": f"entity:{entity.id}", "label": entity.canonical_name, "type": entity.entity_type}
                     for entity in entities)
        for relationship in db.scalars(select(EntityRelationship).where(
            EntityRelationship.case_id == case.id,
            EntityRelationship.source_entity_id.in_(visible_entity_ids),
            EntityRelationship.target_entity_id.in_(visible_entity_ids),
        )):
            if relationship.source_document_version_id:
                version = db.get(DocumentVersion, relationship.source_document_version_id)
                document = db.get(Document, version.document_id) if version else None
                if not document or document.id not in authorized_document_ids:
                    continue
            edges.append({"source": f"entity:{relationship.source_entity_id}",
                          "target": f"entity:{relationship.target_entity_id}",
                          "label": relationship.relationship_type})
        return {"provider": "POSTGRES_FALLBACK", "nodes": nodes, "edges": edges}
