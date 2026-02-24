# Flow Mind (Stage 1) — AI-first Workflow Engine

Flow Mind is a minimal AI-first SaaS backend that converts unstructured business text into structured, validated outputs.

**Key idea:** LLMs are non-deterministic, so we wrap them inside deterministic systems:
- Schema-first extraction (Pydantic validation)
- Deterministic risk scoring (rule engine)
- Observability (request id + timing logs)

---

## What it does (Stage 1)

Input: unstructured text (e.g. onboarding / support / compliance notes)

Output: a structured JSON object:
- entity type / name / jurisdiction
- people involved
- intent
- summary (1–2 sentences)
- **risk_score (0..10) + risk_flags (explainable)**

---

## Quickstart (30 seconds)

### 1) Set env vars

Create `.env` and add OpenAI API key in the global envrionment:

```bash
OPEN_AI_KEY=your_key_here
OPENAI_MODEL=gpt-5-nano
```

Run the application:

```bash
pip install -e .
uvicorn app.main:app --reload
```

Open Swagger:

```bash
http://127.0.0.1:8000/docs
```
