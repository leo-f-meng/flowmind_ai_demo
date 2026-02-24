from fastapi import FastAPI, HTTPException
import time
import uuid
import logging
from .logging_conf import setup_logging
from app.schemas import ExtractionResult, ProcessRequest
from app.risk import calculate_risk
from app.llm import LLMClient, LLMError


app = FastAPI(title="Flow Mind - AI Workflow Engine", version="0.1.1")
llm_client = LLMClient()
setup_logging()
logger = logging.getLogger("flowmind")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/process", response_model=ExtractionResult)
def process(req: ProcessRequest):
    try:
        raw = llm_client.extract_json(req.text)
        result = ExtractionResult.model_validate(raw)

        # override risk score/flags based on our own rules
        new_score, new_flags = calculate_risk(
            result.entity_type, result.jurisdiction, req.text
        )

        result.risk_score = new_score
        result.risk_flags = list(set((result.risk_flags or []) + new_flags))

        return result

    except LLMError as e:
        raise HTTPException(status_code=502, detail=f"LLM extraction failed: {str(e)}")
