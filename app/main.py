from fastapi import FastAPI, HTTPException, BackgroundTasks
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

from sqlalchemy import select
from app.pricing import estimate_cost_usd_micros

app = FastAPI(title="Flow Mind - AI Workflow Engine", version="0.1.1")
llm_client = LLMClient()
setup_logging()
logger = logging.getLogger("flowmind")

Base.metadata.create_all(bind=engine)


def process_run_in_background(run_id):
    start = time.time()
    db = SessionLocal()
    try:
        # 1) load run
        run = db.execute(select(Run).where(Run.id == run_id)).scalar_one()
        run.status = "processing"
        db.commit()

        # 2) LLM extract
        raw, usage = llm_client.extract_json(run.input_text)
        result = ExtractionResult.model_validate(raw)

        # 3) deterministic risk
        new_score, new_flags = calculate_risk(
            result.entity_type, result.jurisdiction, run.input_text
        )
        result.risk_score = new_score
        result.risk_flags = list(dict.fromkeys((result.risk_flags or []) + new_flags))

        # 4) metrics
        latency_ms = int((time.time() - start) * 1000)
        input_tokens = usage["input_tokens"] if usage else None
        output_tokens = usage["output_tokens"] if usage else None
        total_tokens = usage["total_tokens"] if usage else None
        cost_micros = estimate_cost_usd_micros(input_tokens, output_tokens)

        # 5) persist
        run.status = "done"
        run.result_json = result.model_dump()
        run.latency_ms = latency_ms
        run.model = os.getenv("OPENAI_MODEL")
        run.input_tokens = input_tokens
        run.output_tokens = output_tokens
        run.total_tokens = total_tokens
        run.cost_usd_micros = cost_micros
        run.error = None

        db.commit()

    except Exception as e:
        db.rollback()
        # record failure in run
        try:
            run = db.execute(select(Run).where(Run.id == run_id)).scalar_one()
            run.status = "failed"
            run.error = str(e)
            run.latency_ms = int((time.time() - start) * 1000)
            db.commit()
        except Exception:
            db.rollback()
        logger.exception(f"background run failed run_id={run_id}")
    finally:
        db.close()


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

        raw, usage = llm_client.extract_json(req.text)
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


@app.post("/process/async")
def process_async(req: ProcessRequest, background_tasks: BackgroundTasks):
    db = SessionLocal()
    try:
        run = Run(status="queued", input_text=req.text)
        db.add(run)
        db.commit()
        db.refresh(run)

        background_tasks.add_task(process_run_in_background, run.id)

        return {"run_id": str(run.id), "status": run.status}
    finally:
        db.close()


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    db = SessionLocal()
    try:
        # UUID is stored as UUID; SQLAlchemy will coerce if possible
        run = db.execute(select(Run).where(Run.id == run_id)).scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail="run not found")

        return {
            "run_id": str(run.id),
            "status": run.status,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "latency_ms": run.latency_ms,
            "model": run.model,
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
            "total_tokens": run.total_tokens,
            "cost_usd_micros": run.cost_usd_micros,
            "error": run.error,
            "result": run.result_json,
        }
    finally:
        db.close()
