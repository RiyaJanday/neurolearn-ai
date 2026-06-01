from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from db.models import TopicPerformance
from core.rag_engine import get_llm


def classify_mistake(question: str, student_answer: str, correct_answer: str) -> dict:
    """
    Uses LLM to classify what type of mistake the student made.
    Returns: { type: concept|calculation|careless, reason: str }
    """
    try:
        llm = get_llm()
        prompt = f"""A student answered a question incorrectly. Classify the mistake type.

Question: {question}
Student's Answer: {student_answer}
Correct Answer: {correct_answer}

Mistake types:
- concept: Student misunderstood the underlying concept or theory
- calculation: Student understood the concept but made a math/arithmetic error
- careless: Student knew it but made a silly mistake (wrong sign, misread question, etc.)

Reply in EXACTLY this format:
type: <concept|calculation|careless>
reason: <one sentence explaining the mistake>"""

        response = llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)

        result = {"type": "concept", "reason": "Could not classify mistake"}
        for line in text.strip().split("\n"):
            if line.lower().startswith("type:"):
                val = line.split(":", 1)[1].strip().lower()
                if val in ["concept", "calculation", "careless"]:
                    result["type"] = val
            elif line.lower().startswith("reason:"):
                result["reason"] = line.split(":", 1)[1].strip()
        return result

    except Exception:
        return {"type": "concept", "reason": "Classification failed"}


def update_topic_performance(
    db: Session,
    user_id: str,
    subject: str,
    topic: str,
    score: float,
    mistake_type: Optional[str] = None,
    is_ai_query: bool = False,
):
    """
    Update or create a topic performance record.
    Called after every quiz attempt or AI chat query.
    """
    record = (
        db.query(TopicPerformance)
        .filter(
            TopicPerformance.user_id == user_id,
            TopicPerformance.topic == topic,
        )
        .first()
    )

    if not record:
        record = TopicPerformance(
            user_id=user_id,
            subject=subject,
            topic=topic,
            score=score,
        )
        db.add(record)
    else:
        # Rolling average — weight towards recent performance
        record.score = round(0.7 * record.score + 0.3 * score, 2)
        record.last_practiced = datetime.now(timezone.utc)

    # Update counters
    record.total_attempts += 1

    if is_ai_query:
        record.ai_dependency_count += 1

    if mistake_type == "concept":
        record.concept_errors += 1
    elif mistake_type == "calculation":
        record.calc_errors += 1
    elif mistake_type == "careless":
        record.careless_errors += 1

    # Weakness detection logic
    record.is_weak = record.score < 60
    record.is_high_ai_dep = record.ai_dependency_count >= 3 and record.score < 60

    db.commit()
    return record


def get_weakness_report(db: Session, user_id: str) -> list:
    """Full weakness analysis for all topics."""
    records = (
        db.query(TopicPerformance)
        .filter(TopicPerformance.user_id == user_id)
        .order_by(TopicPerformance.score)
        .all()
    )

    result = []
    for r in records:
        # Find dominant mistake type
        dominant = None
        errors = {
            "concept": r.concept_errors,
            "calculation": r.calc_errors,
            "careless": r.careless_errors,
        }
        total_errors = sum(errors.values())
        if total_errors > 0:
            dominant = max(errors, key=errors.get)

        result.append(
            {
                "subject": r.subject,
                "topic": r.topic,
                "score": round(r.score, 1),
                "ai_dependency_count": r.ai_dependency_count,
                "is_weak": r.is_weak,
                "is_high_ai_dep": r.is_high_ai_dep,
                "dominant_mistake": dominant,
                "concept_errors": r.concept_errors,
                "calc_errors": r.calc_errors,
                "careless_errors": r.careless_errors,
                "total_attempts": r.total_attempts,
                "insight": _generate_insight(r, dominant),
                "status": (
                    "strong"
                    if r.score >= 75
                    else "at_risk" if r.score >= 50 else "weak"
                ),
            }
        )
    return result


def _generate_insight(r, dominant_mistake: Optional[str]) -> str:
    """Generate a human-readable insight for a topic."""
    if r.is_high_ai_dep:
        return (
            f"You are relying heavily on AI for {r.topic} "
            f"({r.ai_dependency_count} queries). "
            f"Try solving problems independently first."
        )
    if r.score < 40:
        return f"{r.topic} is critically weak. Start from fundamentals immediately."
    if r.score < 60:
        if dominant_mistake == "concept":
            return (
                f"Your {r.topic} errors suggest conceptual gaps — revisit the theory."
            )
        elif dominant_mistake == "calculation":
            return f"You understand {r.topic} but make calculation errors. Practice more problems."
        elif dominant_mistake == "careless":
            return f"Your {r.topic} mistakes are mostly careless. Slow down and double-check."
        return f"{r.topic} is weak. More practice needed."
    if r.score >= 75:
        return f"{r.topic} is strong. Maintain with periodic revision."
    return f"{r.topic} is progressing. Keep practicing consistently."
