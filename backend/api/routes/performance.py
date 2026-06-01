from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User, TopicPerformance, QuizAttempt, ChatLog, DailyActivity
from core.weakness_engine import get_weakness_report
from core.memory_engine import get_retention_report
from api.routes.auth import get_current_user

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/weakness")
def weakness(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_weakness_report(db, user.id)


@router.get("/retention")
def retention(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_retention_report(db, user.id)


@router.get("/activity")
def activity(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = (
        db.query(DailyActivity)
        .filter(DailyActivity.user_id == user.id)
        .order_by(DailyActivity.date)
        .all()
    )

    return [
        {
            "date": r.date,
            "count": r.chat_count + r.quiz_count + r.notes_count,
            "chat_count": r.chat_count,
            "quiz_count": r.quiz_count,
            "notes_count": r.notes_count,
        }
        for r in records
    ]


@router.get("/summary")
def summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    topics = (
        db.query(TopicPerformance).filter(TopicPerformance.user_id == user.id).all()
    )
    total_quizzes = db.query(QuizAttempt).filter(QuizAttempt.user_id == user.id).count()
    total_chats = (
        db.query(ChatLog)
        .filter(ChatLog.user_id == user.id, ChatLog.is_academic == True)
        .count()
    )

    avg_score = round(sum(t.score for t in topics) / len(topics), 1) if topics else 0
    weak_count = sum(1 for t in topics if t.is_weak)
    high_dep_count = sum(1 for t in topics if t.is_high_ai_dep)

    return {
        "total_topics": len(topics),
        "avg_score": avg_score,
        "weak_topics": weak_count,
        "high_ai_dependency_topics": high_dep_count,
        "total_quizzes": total_quizzes,
        "total_chats": total_chats,
    }
