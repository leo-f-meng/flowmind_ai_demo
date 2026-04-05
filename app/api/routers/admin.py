from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user_role, get_db
from app.knowledge.ingestor import ingest_corpus
from app.models.db import DBFinding

router = APIRouter(prefix="/admin", tags=["admin"])

_VALID_NAMESPACES = {"gdpr", "soc2", "ccpa", "hipaa", "internal_policy"}


class IngestRequest(BaseModel):
    texts: list[str]
    sources: list[str]
    namespace: str = "gdpr"


@router.post("/knowledge/ingest")
def ingest_knowledge(
    body: IngestRequest,
    user_role: tuple[str, str] = Depends(get_current_user_role),
    db: Session = Depends(get_db),
):
    user_id, role = user_role
    if role != "compliance_officer":
        raise HTTPException(status_code=403, detail="Only compliance officers can ingest knowledge.")
    if body.namespace not in _VALID_NAMESPACES:
        raise HTTPException(status_code=422, detail=f"Unknown namespace '{body.namespace}'. Valid: {_VALID_NAMESPACES}")

    count = ingest_corpus(body.texts, body.sources, body.namespace)
    return {"chunks_ingested": count, "namespace": body.namespace}


@router.post("/maintenance/purge-excerpts")
def purge_expired_excerpts(
    user_role: tuple[str, str] = Depends(get_current_user_role),
    db: Session = Depends(get_db),
):
    """Null out clause excerpts that have passed their expiry date."""
    _, role = user_role
    if role != "compliance_officer":
        raise HTTPException(status_code=403, detail="Admin only.")

    now = datetime.now(timezone.utc)
    expired = db.query(DBFinding).filter(
        DBFinding.excerpt_expires_at < now,
        DBFinding.clause_excerpt.isnot(None),
    ).all()

    count = len(expired)
    for finding in expired:
        finding.clause_excerpt = None
        finding.excerpt_expires_at = None
    db.commit()
    return {"purged": count}
