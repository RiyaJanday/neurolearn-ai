from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date

from db.database import get_db
from db.models import QuizAttempt, DailyActivity, User
from core.weakness_engine import classify_mistake, update_topic_performance
from core.memory_engine import mark_topic_reviewed
from api.routes.auth import get_current_user

router = APIRouter(prefix="/quiz", tags=["quiz"])


class QuizSubmitRequest(BaseModel):
    subject: str
    topic: str
    question: str
    student_answer: str
    correct_answer: str


@router.post("/submit")
def submit_quiz(
    req: QuizSubmitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1. Check if answer is correct
    is_correct = (
        req.student_answer.strip().lower() == req.correct_answer.strip().lower()
    )
    score = 100.0 if is_correct else 0.0

    # 2. Classify mistake if wrong
    mistake_type = None
    mistake_reason = None

    if not is_correct:
        result = classify_mistake(req.question, req.student_answer, req.correct_answer)
        mistake_type = result["type"]
        mistake_reason = result["reason"]

    # 3. Save attempt
    attempt = QuizAttempt(
        user_id=user.id,
        subject=req.subject,
        topic=req.topic,
        question=req.question,
        student_answer=req.student_answer,
        correct_answer=req.correct_answer,
        is_correct=is_correct,
        mistake_type=mistake_type,
        mistake_reason=mistake_reason,
        score=score,
    )
    db.add(attempt)

    # 4. Update topic performance
    update_topic_performance(
        db=db,
        user_id=user.id,
        subject=req.subject,
        topic=req.topic,
        score=score,
        mistake_type=mistake_type,
    )

    # 5. Update memory tracking
    mark_topic_reviewed(db, user.id, req.subject, req.topic, score)

    # 6. Update daily activity
    today = date.today().isoformat()
    activity = (
        db.query(DailyActivity)
        .filter(
            DailyActivity.user_id == user.id,
            DailyActivity.date == today,
        )
        .first()
    )

    if activity:
        activity.quiz_count += 1
    else:
        db.add(
            DailyActivity(
                user_id=user.id,
                date=today,
                quiz_count=1,
            )
        )

    db.commit()

    return {
        "is_correct": is_correct,
        "score": score,
        "mistake_type": mistake_type,
        "mistake_reason": mistake_reason,
    }


@router.get("/history")
def quiz_history(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == user.id)
        .order_by(QuizAttempt.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": a.id,
            "subject": a.subject,
            "topic": a.topic,
            "question": a.question,
            "is_correct": a.is_correct,
            "mistake_type": a.mistake_type,
            "mistake_reason": a.mistake_reason,
            "score": a.score,
            "created_at": a.created_at,
        }
        for a in attempts
    ]
