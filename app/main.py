from fastapi import FastAPI, HTTPException
from typing import List
import time
import uuid
import logging
from app.logging_conf import setup_logging
from app.schemas import ExtractionResult, ProcessRequest
from app.risk import calculate_risk
from app.llm import LLMClient, LLMError
from app.examples import EXAMPLES

app = FastAPI(title="Flow Mind - AI Workflow Engine", version="0.1.1")
llm_client = LLMClient()
setup_logging()
logger = logging.getLogger("flowmind")


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

    try:
        logger.info(f"[{request_id}] /process start chars={len(req.text)}")

        raw = llm_client.extract_json(req.text)
        result = ExtractionResult.model_validate(raw)

        new_score, new_flags = calculate_risk(
            result.entity_type, result.jurisdiction, req.text
        )
        result.risk_score = new_score
        result.risk_flags = list(set((result.risk_flags or []) + new_flags))

        ms = int((time.time() - start) * 1000)
        logger.info(
            f"[{request_id}] /process ok ms={ms} "
            f"entity={result.entity_type} risk={result.risk_score} flags={len(result.risk_flags)}"
        )
        return result

    except LLMError as e:
        ms = int((time.time() - start) * 1000)
        logger.error(f"[{request_id}] /process llm_error ms={ms} err={str(e)}")
        raise HTTPException(
            status_code=502, detail=f"LLM extraction failed (id={request_id})"
        )

    except Exception as e:
        ms = int((time.time() - start) * 1000)
        logger.exception(f"[{request_id}] /process unexpected_error ms={ms}")
        raise


@app.post("/process/batch", response_model=List[ExtractionResult])
def process_batch(reqs: List[ProcessRequest]):
    results = []
    for r in reqs:
        results.append(process(r))
    return results
