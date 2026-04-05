# Compliance Analysis Agent

An AI-powered pre-review system for supplier contracts and data protection agreements. Uploads a document, runs it through a GDPR compliance pipeline, and returns a Red / Amber / Green risk score. Red-scored contracts are hard-blocked from proceeding until a compliance officer overrides with a documented reason.

## What It Does

- Accepts PDF and DOCX supplier contracts via a REST API
- Classifies documents (DPA, MSA, NDA, SOW, Privacy Policy)
- Extracts clauses and checks each against ~40 GDPR Article 28/32 requirements
- Scores findings using pure Python rules — no LLM involved in the gate decision
- Hard-blocks Red-scored contracts; requires compliance officer override with audit trail
- Stores encrypted clause excerpts for reviewer context (auto-purged after 30 days)

## Tech Stack

| Layer             | Technology                           |
| ----------------- | ------------------------------------ |
| Language          | Python 3.12+                         |
| API               | FastAPI                              |
| LLM Orchestration | LangChain + LangGraph                |
| LLM               | OpenAI GPT-4o / GPT-4o-mini          |
| Embeddings        | OpenAI `text-embedding-3-small`      |
| Vector Store      | Pinecone (serverless, namespaced)    |
| Database          | PostgreSQL 16 (SQLAlchemy + Alembic) |
| Document Parsing  | PyMuPDF, python-docx                 |
| Deployment        | Docker + Docker Compose              |

## Quick Start

```bash
# 1. Copy environment config
cp .env.example .env
# Fill in OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME

# 2. Start services
docker compose up -d

# 3. Run database migrations
alembic upgrade head

# 4. Verify health
curl http://localhost:8000/health
# → {"status": "ok"}

# 5. Open API docs
open http://localhost:8000/docs
```

## API Overview

| Method | Path                      | Description                            |
| ------ | ------------------------- | -------------------------------------- |
| `POST` | `/jobs/upload`            | Upload a contract document             |
| `GET`  | `/jobs/{job_id}`          | Poll job status and RAG score          |
| `GET`  | `/jobs/{job_id}/findings` | View per-requirement findings          |
| `POST` | `/jobs/{job_id}/override` | Compliance officer override            |
| `GET`  | `/jobs`                   | List your submitted jobs               |
| `POST` | `/admin/knowledge/ingest` | Ingest regulatory corpus into Pinecone |

All requests require an `X-User-Id` header. Role-sensitive endpoints also require `X-User-Role`.

## Pipeline

```
Upload → parse_document → extract_clauses → check_gdpr → aggregate_risk → gate_decision
                                                 ↑
                                    [checklist + Pinecone RAG]
```

## Risk Score

| Score    | Meaning                               | Action                                         |
| -------- | ------------------------------------- | ---------------------------------------------- |
| 🔴 RED   | Critical finding or ≥ 2 High findings | Blocked — compliance officer override required |
| 🟡 AMBER | 1 High or ≥ 3 Medium or ≥ 5 Unclear   | Escalated — reviewer sign-off required         |
| 🟢 GREEN | No significant issues found           | Auto-cleared and logged                        |

## Project Docs

- [Project Overview](docs/project-overview.md)
- [Scope](docs/scope.md)
- [Use Cases](docs/use-cases.md)
- [RAG Data Strategy](docs/rag-data-strategy.md)
- [Rule Engine vs Vector DB](docs/rule-engine-vs-vector-db.md)
- [Output Schema](docs/output-schema.md)
- [Guardrails](docs/guardrails.md)
- [Evaluation Plan](docs/evaluation-plan.md)
- [Demo Script](docs/demo-script.md)
- [Design Spec](docs/superpowers/specs/2026-04-02-compliance-analysis-agent-design.md)
- [Implementation Plan](docs/superpowers/plans/2026-04-02-compliance-analysis-agent.md)
