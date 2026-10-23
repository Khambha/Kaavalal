from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.alert import Alert

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("/published")
def published_alerts(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Alert)
        .filter(Alert.status == "published")
        .order_by(Alert.published_at.desc())
        .all()
    )
    return [
        {
            "id": alert.id,
            "title": alert.title,
            "message": alert.message,
            "severity": alert.severity,
            "district": alert.district,
            "published_at": alert.published_at,
            "expires_at": alert.expires_at,
        }
        for alert in rows
        if alert.expires_at is None or (alert.expires_at.replace(tzinfo=timezone.utc) if alert.expires_at.tzinfo is None else alert.expires_at) > now
    ]
