import math
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy.orm import Session
from db.models import MemoryTracking, StudyPlan


def calculate_retention(last_reviewed: datetime, decay_rate: float) -> float:
    """
    Ebbinghaus Forgetting Curve formula:
    R = 100 * e^(-decay_rate * days_since_review)

    decay_rate:
      0.07 = slow forgetting (strong topic)
      0.10 = normal forgetting
      0.15 = fast forgetting (weak topic)
    """
    now = datetime.now(timezone.utc)
    if last_reviewed.tzinfo is None:
        last_reviewed = last_reviewed.replace(tzinfo=timezone.utc)

    days = (now - last_reviewed).total_seconds() / 86400
    retention = 100 * math.exp(-decay_rate * days)
    return max(0.0, round(retention, 2))


def days_until_forget(decay_rate: float, last_reviewed: datetime, threshold: float = 40.0) -> float:
    """How many days until retention drops below threshold."""
    now = datetime.now(timezone.utc)
    if last_reviewed.tzinfo is None:
        last_reviewed = last_reviewed.replace(tzinfo=timezone.utc)

    days_elapsed = (now - last_reviewed).total_seconds() / 86400
    # Solve: threshold = 100 * e^(-k*t) => t = -ln(threshold/100) / k
    total_days = -math.log(threshold / 100) / decay_rate
    remaining  = total_days - days_elapsed
    return max(0.0, round(remaining, 1))


def mark_topic_reviewed(
    db: Session,
    user_id: str,
    subject: str,
    topic: str,
    score: float
):
    """
    Called after every quiz or study session.
    Resets retention to 100, adjusts decay rate based on score.
    """
    # Adjust decay rate based on performance
    if score >= 80:
        decay = 0.07   # Strong — forgetting slowly
    elif score >= 60:
        decay = 0.10   # Average — normal forgetting
    else:
        decay = 0.15   # Weak — forgetting quickly

    record = db.query(MemoryTracking).filter(
        MemoryTracking.user_id == user_id,
        MemoryTracking.topic   == topic,
    ).first()

    if record:
        record.retention_score = 100.0
        record.decay_rate      = decay
        record.last_reviewed   = datetime.now(timezone.utc)
    else:
        record = MemoryTracking(
            user_id         = user_id,
            subject         = subject,
            topic           = topic,
            retention_score = 100.0,
            decay_rate      = decay,
            last_reviewed   = datetime.now(timezone.utc),
        )
        db.add(record)

    db.commit()


def update_all_retentions(db: Session, user_id: str):
    """Recalculate retention scores for all topics of a user."""
    records = db.query(MemoryTracking).filter(
        MemoryTracking.user_id == user_id
    ).all()

    for r in records:
        r.retention_score = calculate_retention(r.last_reviewed, r.decay_rate)

        # Auto-schedule revision if retention is low
        if r.retention_score < 40:
            already_scheduled = db.query(StudyPlan).filter(
                StudyPlan.user_id == user_id,
                StudyPlan.topic   == r.topic,
                StudyPlan.status  == "pending",
            ).first()

            if not already_scheduled:
                plan = StudyPlan(
                    user_id        = user_id,
                    subject        = r.subject,
                    topic          = r.topic,
                    priority       = 1,
                    scheduled_date = datetime.now(timezone.utc) + timedelta(hours=1),
                    status         = "pending",
                )
                db.add(plan)

    db.commit()


def get_retention_report(db: Session, user_id: str) -> List[dict]:
    """Return full retention status for all tracked topics."""
    update_all_retentions(db, user_id)

    records = db.query(MemoryTracking).filter(
        MemoryTracking.user_id == user_id
    ).order_by(MemoryTracking.retention_score).all()

    result = []
    for r in records:
        result.append({
            "subject":         r.subject,
            "topic":           r.topic,
            "retention_score": round(r.retention_score, 1),
            "decay_rate":      r.decay_rate,
            "last_reviewed":   r.last_reviewed.isoformat(),
            "days_until_forget": days_until_forget(r.decay_rate, r.last_reviewed),
            "needs_revision":  r.retention_score < 40,
            "status": (
                "critical" if r.retention_score < 40 else
                "at_risk"  if r.retention_score < 70 else
                "good"
            ),
        })
    return result