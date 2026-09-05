from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Case, Document, DocumentVersion, User


class UserRepository:
    def by_email(self, db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(User.email == email.lower()))


class CaseRepository:
    def by_number(self, db: Session, case_number: str) -> Case | None:
        return db.scalar(select(Case).where(Case.case_number == case_number))

    def list(self, db: Session) -> list[Case]:
        return list(db.scalars(select(Case).order_by(Case.updated_at.desc())))


class DocumentRepository:
    def by_id(self, db: Session, document_id: str) -> Document | None:
        return db.get(Document, document_id)

    def version(self, db: Session, version_id: str) -> DocumentVersion | None:
        return db.get(DocumentVersion, version_id)
