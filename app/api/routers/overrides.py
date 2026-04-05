from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user_role, get_db
from app.models.db import Job, Override, DBFinding, EventLog
from datetime import datetime, timezone

router = APIRouter(prefix="/jobs", tags=["overrides"])

_VALID_MITIGATING_CONTROLS = [
    "existing_dpa_under_negotiation",
    "legal_team_reviewed",
    "compensating_security_controls",
    "dpia_completed",
    "transfer_impact_assessment_done",
    "supplier_security_audit_completed",
    "contractual_amendment_in_progress",
    "data_minimisation_implemented",
    "encryption_deployed",
]


class OverrideRequest(BaseModel):
    reason: str
    mitigating_controls: list[str]

    @field_validator("reason")
    @classmethod
    def reason_min_length(cls, v):
        if len(v.strip()) < 50:
            raise ValueError("Override reason must be at least 50 characters.")
        return v

    @field_validator("mitigating_controls")
    @classmethod
    def controls_not_empty(cls, v):
        if not v:
            raise ValueError("At least one mitigating control must be selected.")
        return v


@router.post("/{job_id}/override")
def override_job(
    job_id: UUID,
    body: OverrideRequest,
    user_role: tuple[str, str] = Depends(get_current_user_role),
    db: Session = Depends(get_db),
):
    user_id, role = user_role

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Rule: only compliance_officer can override RED
    if job.rag_score == "RED" and role != "compliance_officer":
        raise HTTPException(status_code=403, detail="Only a compliance officer can override a RED-scored document.")

    # Rule: no self-override
    if job.uploaded_by == user_id:
        raise HTTPException(status_code=403, detail="The document uploader cannot override their own document.")

    # Validate controls against predefined list
    invalid = [c for c in body.mitigating_controls if c not in _VALID_MITIGATING_CONTROLS]
    if invalid:
        raise HTTPException(status_code=422, detail=f"Unknown mitigating controls: {invalid}")

    # Snapshot findings at time of override
    findings = db.query(DBFinding).filter(DBFinding.job_id == job_id).all()
    findings_snapshot = [
        {"requirement_id": f.requirement_id, "severity": f.severity, "status": f.status, "confidence": f.confidence}
        for f in findings
    ]

    override = Override(
        job_id=job_id,
        reviewer_id=user_id,
        original_score=job.rag_score,
        override_reason=body.reason,
        mitigating_controls=body.mitigating_controls,
        findings_snapshot=findings_snapshot,
    )
    db.add(override)

    job.gate_decision = "CLEARED"
    job.status = "overridden"

    db.add(EventLog(
        job_id=job_id,
        actor=user_id,
        event_type="override",
        detail={"original_score": job.rag_score, "reason_length": len(body.reason)},
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()

    return {"status": "overridden", "job_id": str(job_id), "reviewer": user_id}
