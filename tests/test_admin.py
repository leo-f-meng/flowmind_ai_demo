import pytest
import uuid as _uuid_mod
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, JSON, String, StaticPool, event, Uuid as SAUuid
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from app.models.db import Base, Job, DBFinding
from app.database import get_db
from main import app

# ── SQLite compatibility: patch PG-specific column types once at import time ──
#
# Two-pronged fix:
# 1. Patch SAUuid.bind_processor so the ORM emits hyphenated UUID strings for
#    WHERE clauses (which are affected by the cached type processor).
# 2. Register a before_cursor_execute engine event to coerce any UUID objects
#    that slip through into parameters (e.g. for FK columns on INSERT).

def _sqlite_uuid_bind_processor(self, dialect):
    def process(value):
        if value is None:
            return None
        return str(value)
    return process

SAUuid.bind_processor = _sqlite_uuid_bind_processor

for table in Base.metadata.tables.values():
    for col in table.columns:
        if isinstance(col.type, JSONB):
            col.type = JSON()
        elif isinstance(col.type, PGUUID):
            col.type = String(36)
            # Also patch the default so it returns a str, not a UUID object
            if col.default is not None and col.default.is_callable:
                col.default.arg = lambda ctx: str(_uuid_mod.uuid4())

# Use StaticPool so all connections in all threads share the same in-memory DB
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def _coerce_params(params):
    """Recursively coerce UUID objects to str in query parameters."""
    if isinstance(params, (list, tuple)):
        coerced = [str(p) if isinstance(p, _uuid_mod.UUID) else p for p in params]
        return type(params)(coerced)
    if isinstance(params, dict):
        return {k: str(v) if isinstance(v, _uuid_mod.UUID) else v for k, v in params.items()}
    return params


@event.listens_for(_engine, "before_cursor_execute", retval=True)
def _coerce_uuids(conn, cursor, statement, parameters, context, executemany):
    return statement, _coerce_params(parameters)


Base.metadata.create_all(_engine)
_TestSession = sessionmaker(bind=_engine)


@pytest.fixture
def client_with_expired_findings():
    # Recreate tables fresh for each test to avoid state leakage
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)

    session = _TestSession()

    job = Job(filename_hash="abc", uploaded_by="x@x.com")
    session.add(job)
    session.commit()

    expired = DBFinding(
        job_id=job.id,
        requirement_id="ART28_DPA_EXECUTED",
        severity="critical",
        status="absent",
        confidence=0.9,
        clause_excerpt="some encrypted text",
        excerpt_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session.add(expired)
    session.commit()
    session.close()

    def override_db():
        db = _TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_purge_expired_excerpts(client_with_expired_findings):
    response = client_with_expired_findings.post(
        "/admin/maintenance/purge-excerpts",
        headers={"x-user-id": "officer@example.com", "x-user-role": "compliance_officer"},
    )
    assert response.status_code == 200
    assert response.json()["purged"] == 1


def test_purge_non_officer_forbidden(client_with_expired_findings):
    response = client_with_expired_findings.post(
        "/admin/maintenance/purge-excerpts",
        headers={"x-user-id": "reviewer@example.com", "x-user-role": "reviewer"},
    )
    assert response.status_code == 403
