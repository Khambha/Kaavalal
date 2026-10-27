from app.models.shelter import RequestStatusEvent


def record_status(db, *, status, actor_role="system", note=None, help_request_id=None, shelter_request_id=None):
    db.add(RequestStatusEvent(
        help_request_id=help_request_id,
        shelter_request_id=shelter_request_id,
        status=status,
        note=note,
        actor_role=actor_role,
    ))


def event_public(event):
    return {"id": event.id, "status": event.status, "note": event.note,
            "actor_role": event.actor_role, "created_at": event.created_at}
