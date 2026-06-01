from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import aiofiles
import os
import uuid

from db.database import get_db
from db.models import Note, DailyActivity, User
from core.rag_engine import add_to_vectorstore, extract_text_from_pdf
from api.routes.auth import get_current_user
from datetime import date

router = APIRouter(prefix="/notes", tags=["notes"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def transform_notes(text: str) -> dict:
    """Convert raw text into summary, flashcards, exam questions."""
    from core.rag_engine import get_llm
    import json

    llm = get_llm()

    # Summary
    summary_resp = llm.invoke(
        f"Summarize these study notes in 5 clear bullet points. Be concise.\n\nNotes:\n{text[:3000]}"
    )
    summary = (
        summary_resp.content if hasattr(summary_resp, "content") else str(summary_resp)
    )

    # Flashcards
    flash_resp = llm.invoke(f"""Create 5 flashcards from these notes.
Reply ONLY with a valid JSON array, no markdown, no extra text:
[{{"front": "question", "back": "answer"}}]

Notes:
{text[:3000]}""")
    flash_text = (
        flash_resp.content if hasattr(flash_resp, "content") else str(flash_resp)
    )
    try:
        clean = (
            flash_text.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        flashcards = json.loads(clean)
    except Exception:
        flashcards = [{"front": "Review these notes", "back": "See uploaded document"}]

    # Exam questions
    exam_resp = llm.invoke(
        f"""Generate 5 exam questions from these notes at varying difficulty.
Reply ONLY with a valid JSON array, no markdown:
[{{"question": "...", "answer": "...", "difficulty": "easy|medium|hard"}}]

Notes:
{text[:3000]}"""
    )
    exam_text = exam_resp.content if hasattr(exam_resp, "content") else str(exam_resp)
    try:
        clean = (
            exam_text.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        exam_questions = json.loads(clean)
    except Exception:
        exam_questions = [
            {
                "question": "Review the uploaded notes",
                "answer": "See document",
                "difficulty": "medium",
            }
        ]

    return {
        "summary": summary.strip(),
        "flashcards": flashcards,
        "exam_questions": exam_questions,
    }


@router.post("/upload")
async def upload_note(
    file: UploadFile = File(...),
    subject: Optional[str] = None,
    topic: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Save file temporarily
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Extract text
    raw_text = extract_text_from_pdf(file_path)
    if not raw_text.strip():
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail="Could not extract text. Ensure PDF has selectable text.",
        )

    # Transform notes using LLM
    transformed = transform_notes(raw_text)

    # Index in FAISS vector store
    meta = {
        "source": file.filename,
        "subject": subject or "",
        "topic": topic or "",
    }
    add_to_vectorstore(user.id, [raw_text], [meta])

    # Save to database
    note = Note(
        user_id=user.id,
        filename=file.filename,
        subject=subject,
        topic=topic,
        raw_text=raw_text,
        summary=transformed["summary"],
        flashcards=transformed["flashcards"],
        exam_questions=transformed["exam_questions"],
        is_indexed=True,
    )
    db.add(note)

    # Update daily activity
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
        activity.notes_count += 1
    else:
        db.add(DailyActivity(user_id=user.id, date=today, notes_count=1))

    db.commit()

    # Delete temp file
    os.remove(file_path)

    return {
        "id": note.id,
        "filename": note.filename,
        "summary": transformed["summary"],
        "flashcards": transformed["flashcards"],
        "exam_questions": transformed["exam_questions"],
    }


@router.get("")
def get_notes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notes = (
        db.query(Note)
        .filter(Note.user_id == user.id)
        .order_by(Note.created_at.desc())
        .all()
    )

    return [
        {
            "id": n.id,
            "filename": n.filename,
            "subject": n.subject,
            "topic": n.topic,
            "summary": n.summary,
            "flashcards": n.flashcards,
            "exam_questions": n.exam_questions,
            "created_at": n.created_at,
        }
        for n in notes
    ]
