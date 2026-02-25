from fastapi import FastAPI, HTTPException
import os
from typing import List
import time
import uuid
import logging
from app.logging_conf import setup_logging
from app.schemas import ExtractionResult, ProcessRequest
from app.risk import calculate_risk
from app.llm import LLMClient, LLMError
from app.examples import EXAMPLES
from app.db import engine
from app.models import Base
from app.db import SessionLocal
from app.models import Run

app = FastAPI(title="Flow Mind - AI Workflow Engine", version="0.1.1")
llm_client = LLMClient()
setup_logging()
logger = logging.getLogger("flowmind")

Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/examples")
def examples():
    return EXAMPLES


@app.post("/process", response_model=ExtractionResult)
def process(req: ProcessRequest):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()

    db = SessionLocal()

    try:
        logger.info(f"[{request_id}] /process start chars={len(req.text)}")

        raw = llm_client.extract_json(req.text)
        result = ExtractionResult.model_validate(raw)

        new_score, new_flags = calculate_risk(
            result.entity_type, result.jurisdiction, req.text
        )
        result.risk_score = new_score
        result.risk_flags = list(dict.fromkeys((result.risk_flags or []) + new_flags))

        latency_ms = int((time.time() - start) * 1000)

        logger.info(
            f"[{request_id}] /process ok ms={latency_ms} "
            f"entity={result.entity_type} risk={result.risk_score} flags={len(result.risk_flags)}"
        )
        run = Run(
            status="done",
            input_text=req.text,
            result_json=result.model_dump(),
            latency_ms=latency_ms,
            model=os.getenv("OPENAI_MODEL"),
        )

        db.add(run)
        db.commit()
        db.refresh(run)

        logger.info(f"[{request_id}] done run_id={run.id}")

        return result

    except LLMError as e:
        ms = int((time.time() - start) * 1000)
        logger.error(f"[{request_id}] /process llm_error ms={ms} err={str(e)}")
        raise HTTPException(
            status_code=502, detail=f"LLM extraction failed (id={request_id})"
        )

    except Exception as e:
        db.rollback()
        ms = int((time.time() - start) * 1000)
        logger.exception(f"[{request_id}] /process unexpected_error ms={ms}")
        raise

    finally:
        db.close()


@app.post("/process/batch", response_model=List[ExtractionResult])
def process_batch(reqs: List[ProcessRequest]):
    results = []
    for r in reqs:
        results.append(process(r))
    return results
