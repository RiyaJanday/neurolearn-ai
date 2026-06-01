from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date

from db.database import get_db
from db.models import ChatLog, DailyActivity, TopicPerformance, User
from core.rag_engine import query_rag
from core.classifier import classify_query, extract_topic, detect_language
from core.weakness_engine import update_topic_performance
from core.memory_engine import mark_topic_reviewed
from api.routes.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = None


@router.post("")
def chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1. Detect language
    lang = req.language or detect_language(req.message)

    # 2. Check if academic
    is_academic = classify_query(req.message)

    if not is_academic:
        # Log rejected query
        log = ChatLog(
            user_id=user.id,
            query=req.message,
            answer="REJECTED",
            is_academic=False,
            language=lang,
        )
        db.add(log)
        db.commit()

        return {
            "answer": "This chatbot is restricted to academic queries only. Please ask a study-related question.",
            "is_academic": False,
            "subject": None,
            "topic": None,
            "sources": [],
            "confidence": 1.0,
            "ai_dependency_warning": False,
            "language": lang,
        }

    # 3. Extract subject and topic
    topic_info = extract_topic(req.message)
    subject = topic_info.get("subject", "General")
    topic = topic_info.get("topic", "Unknown")

    # 4. Query RAG engine
    result = query_rag(user.id, req.message, language=lang)

    # 5. Save chat log
    log = ChatLog(
        user_id=user.id,
        query=req.message,
        answer=result["answer"],
        subject=subject,
        topic=topic,
        confidence=result["confidence"],
        sources=result["sources"],
        is_academic=True,
        language=lang,
    )
    db.add(log)

    # 6. Update AI dependency count for this topic
    update_topic_performance(
        db=db,
        user_id=user.id,
        subject=subject,
        topic=topic,
        score=50,  # neutral score for chat queries
        is_ai_query=True,
    )

    # 7. Update daily activity
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
        activity.chat_count += 1
    else:
        db.add(
            DailyActivity(
                user_id=user.id,
                date=today,
                chat_count=1,
            )
        )

    db.commit()

    # 8. Check AI dependency warning
    tp = (
        db.query(TopicPerformance)
        .filter(
            TopicPerformance.user_id == user.id,
            TopicPerformance.topic == topic,
        )
        .first()
    )
    ai_warning = bool(tp and tp.is_high_ai_dep)

    return {
        "answer": result["answer"],
        "is_academic": True,
        "subject": subject,
        "topic": topic,
        "sources": result["sources"],
        "confidence": result["confidence"],
        "ai_dependency_warning": ai_warning,
        "language": lang,
    }


@router.get("/history")
def get_history(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(ChatLog)
        .filter(
            ChatLog.user_id == user.id,
            ChatLog.is_academic == True,
        )
        .order_by(ChatLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": l.id,
            "query": l.query,
            "answer": l.answer,
            "subject": l.subject,
            "topic": l.topic,
            "confidence": l.confidence,
            "created_at": l.created_at,
        }
        for l in logs
    ]
