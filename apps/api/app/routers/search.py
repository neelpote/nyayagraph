from typing import Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..ai.schemas import CaseSearchRequest
from ..ai.search_service import SearchService
from ..database import get_db
from ..graph.service import GraphService
from ..security.auth import AuthenticatedUser, get_current_user

router = APIRouter(tags=["search", "graph"])


@router.get("/search")
def search(
    mode: Literal["metadata", "fulltext", "semantic"] = Query(...),
    q: str = Query(..., min_length=1, max_length=500),
    actor: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"mode": mode, "query": q, "results": SearchService().search(db, actor, q, mode)}


@router.post("/search/case")
def natural_case_search(
    request: CaseSearchRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return SearchService().natural_case_search(db, actor, request.query, request.caseNumber)


@router.get("/cases/{case_number}/graph-v2")
def authorized_case_graph(
    case_number: str,
    actor: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Authorization-safe graph endpoint pending replacement of the legacy demo route."""
    return GraphService().case_graph(db, actor, case_number)
