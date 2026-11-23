"""Recover queued resource triage jobs: python -m app.workers.resource_triage_worker"""
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_

from app.core.database import SessionLocal
from app.models.resource_request_batch import ResourceRequestBatch
from app.services.resource_request_triage import process_resource_request_batch


def run(poll_seconds: int = 5):
    while True:
        db = SessionLocal()
        try:
            stale_before = datetime.now(timezone.utc) - timedelta(minutes=5)
            batch_ids = [row.id for row in db.query(ResourceRequestBatch.id)
                         .filter(or_(ResourceRequestBatch.triage_state == "PENDING",
                                     and_(ResourceRequestBatch.triage_state == "PROCESSING",
                                          ResourceRequestBatch.triage_started_at < stale_before)))
                         .order_by(ResourceRequestBatch.created_at.asc()).limit(20).all()]
        finally:
            db.close()
        for batch_id in batch_ids:
            process_resource_request_batch(batch_id)
        if not batch_ids:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    run()
