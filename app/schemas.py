from typing import Annotated, List, Optional, Literal
from pydantic import BaseModel, Field

EntityType = Literal["company", "individual", "unknown"]


class ProcessRequest(BaseModel):
    text: str = Field(
        ..., min_length=10, description="Unstructured business text to process"
    )
    context: dict | None = Field(
        default=None, description="Optional metadata about the input"
    )


class ExtractionResult(BaseModel):
    entity_type: EntityType
    entity_name: str = Field(..., min_length=1)
    jurisdiction: Optional[str] = None
    people: List[str] = Field(default_factory=list)
    intent: Optional[str] = None

    # Filled by either LLM or rule engine; we will re-score in risk.py
    risk_flags: List[str] = Field(default_factory=list)
    risk_score: Annotated[int, Field(ge=0, le=10, strict=True)] = 0
    summary: str = Field(..., min_length=5, description="1-2 sentence summary")
