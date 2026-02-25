from sqlalchemy import select
from .db import SessionLocal
from .models import Run


def main():
    db = SessionLocal()
    try:
        r = Run(
            status="done",
            input_text="Test input text for DB insert",
            result_json={"hello": "world"},
            latency_ms=123,
            model="test-model",
            total_tokens=42,
            cost_usd_micros=1000,
        )
        db.add(r)
        db.commit()
        db.refresh(r)

        row = db.execute(select(Run).where(Run.id == r.id)).scalar_one()
        print("Inserted run id:", row.id)
        print("Fetched status:", row.status)
        print("Fetched result_json:", row.result_json)
    finally:
        db.close()


if __name__ == "__main__":
    main()
