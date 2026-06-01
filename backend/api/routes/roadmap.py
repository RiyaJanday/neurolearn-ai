from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json

from db.database import get_db
from db.models import StudyPlan, User
from core.weakness_engine import get_weakness_report
from core.rag_engine import get_llm
from api.routes.auth import get_current_user

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


@router.get("")
def get_roadmap(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plans = (
        db.query(StudyPlan)
        .filter(StudyPlan.user_id == user.id)
        .order_by(StudyPlan.scheduled_date)
        .all()
    )

    return [
        {
            "id": p.id,
            "subject": p.subject,
            "topic": p.topic,
            "priority": p.priority,
            "scheduled_date": p.scheduled_date,
            "status": p.status,
        }
        for p in plans
    ]


@router.post("/generate")
def generate_roadmap(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Get weak topics
    weakness = get_weakness_report(db, user.id)
    weak_topics = [w["topic"] for w in weakness if w["is_weak"]]

    # Calculate days until exam
    days = 30
    if user.exam_date:
        try:
            exam_dt = datetime.strptime(user.exam_date, "%Y-%m")
            days = max(1, (exam_dt - datetime.now()).days)
        except Exception:
            pass

    days = min(days, 30)  # cap at 30 days

    llm = get_llm()
    prompt = f"""Create a {days}-day study roadmap for a student.

Exam: {user.exam_target or 'General Exam'}
Subjects: {', '.join(user.subjects or [])}
Weak topics to prioritise: {', '.join(weak_topics) if weak_topics else 'None yet'}

Generate the plan as a JSON array (show max 14 days).
Reply ONLY with the JSON array, no markdown:
[
  {{
    "day": 1,
    "subject": "Mathematics",
    "topic": "Integration",
    "duration_hours": 2,
    "task": "Study integration by parts with 10 practice problems",
    "priority": "high"
  }}
]"""

    response = llm.invoke(prompt)
    text = response.content if hasattr(response, "content") else str(response)

    try:
        clean = (
            text.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        plan = json.loads(clean)
    except Exception:
        plan = [
            {
                "day": 1,
                "subject": user.subjects[0] if user.subjects else "General",
                "topic": weak_topics[0] if weak_topics else "Start studying",
                "duration_hours": 2,
                "task": "Review fundamentals and practice problems",
                "priority": "high",
            }
        ]

    return plan


@router.patch("/{plan_id}/complete")
def complete_task(
    plan_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = (
        db.query(StudyPlan)
        .filter(
            StudyPlan.id == plan_id,
            StudyPlan.user_id == user.id,
        )
        .first()
    )

    if not plan:
        raise HTTPException(status_code=404, detail="Task not found")

    plan.status = "done"
    db.commit()
    return {"message": "Task marked as complete"}
