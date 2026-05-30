from dotenv import load_dotenv

load_dotenv()

from core.rag_engine import get_llm

ACADEMIC_KEYWORDS = [
    "math",
    "mathematics",
    "algebra",
    "calculus",
    "geometry",
    "trigonometry",
    "physics",
    "chemistry",
    "biology",
    "science",
    "history",
    "geography",
    "economics",
    "programming",
    "computer",
    "coding",
    "algorithm",
    "literature",
    "english",
    "grammar",
    "theorem",
    "equation",
    "formula",
    "derivative",
    "integral",
    "reaction",
    "atom",
    "cell",
    "force",
    "jee",
    "neet",
    "gate",
    "exam",
    "syllabus",
    "chapter",
    "concept",
    "define",
    "explain",
    "what is",
    "how does",
    "why is",
    "solve",
]

NON_ACADEMIC_KEYWORDS = [
    "joke",
    "meme",
    "movie",
    "cricket",
    "ipl",
    "bollywood",
    "recipe",
    "cook",
    "dating",
    "girlfriend",
    "boyfriend",
    "stock",
    "crypto",
    "bitcoin",
    "weather",
    "news",
    "instagram",
    "youtube",
    "tiktok",
    "game",
    "pubg",
    "free fire",
    "netflix",
    "web series",
]


def classify_query(query: str) -> bool:
    """
    Returns True if query is academic, False otherwise.
    First checks keywords (fast), then asks LLM (accurate).
    """
    q_lower = query.lower()

    # Fast check — non-academic signals
    if any(word in q_lower for word in NON_ACADEMIC_KEYWORDS):
        return False

    # Fast check — academic signals
    if any(word in q_lower for word in ACADEMIC_KEYWORDS):
        return True

    # Ambiguous — ask LLM
    try:
        llm = get_llm()
        prompt = f"""Is this question related to academic study, learning, or education?
Academic topics include: math, science, history, programming, exam preparation, concepts, formulas.

Reply with ONLY one word: ACADEMIC or NOT_ACADEMIC

Question: {query}"""

        response = llm.invoke(prompt)
        result = (
            response.content.strip().upper()
            if hasattr(response, "content")
            else str(response).strip().upper()
        )
        return "ACADEMIC" in result

    except Exception:
        return True  # if classifier fails, allow the query


def extract_topic(query: str) -> dict:
    """
    Extracts subject and specific topic from a query.
    Returns dict with 'subject' and 'topic' keys.
    """
    try:
        llm = get_llm()
        prompt = f"""From this academic question, identify the subject and specific topic.

Reply in EXACTLY this format, nothing else:
subject: <subject name>
topic: <specific topic name>

Question: {query}

Examples:
Question: What is integration by parts?
subject: Mathematics
topic: Integration

Question: Explain Newton's second law
subject: Physics
topic: Newton's Laws of Motion"""

        response = llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)

        result = {"subject": "General", "topic": "Unknown"}
        for line in text.strip().split("\n"):
            if line.lower().startswith("subject:"):
                result["subject"] = line.split(":", 1)[1].strip().title()
            elif line.lower().startswith("topic:"):
                result["topic"] = line.split(":", 1)[1].strip().title()
        return result

    except Exception:
        return {"subject": "General", "topic": "Unknown"}


def detect_language(text: str) -> str:
    """Detect language of the query."""
    try:
        from langdetect import detect

        return detect(text)
    except Exception:
        return "en"
