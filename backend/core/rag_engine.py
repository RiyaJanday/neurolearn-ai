import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

VECTOR_STORE_PATH = Path("vector_store")
VECTOR_STORE_PATH.mkdir(parents=True, exist_ok=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


def get_embeddings():
    """HuggingFace embeddings — free, runs locally."""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_llm():
    """Groq LLM — free tier, very fast."""
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model_name=GROQ_MODEL,
        temperature=0.1,
        max_tokens=1024,
    )


def get_vectorstore(user_id: str) -> Optional[FAISS]:
    """Load existing FAISS index for a user."""
    index_path = VECTOR_STORE_PATH / user_id
    if index_path.exists():
        embeddings = get_embeddings()
        return FAISS.load_local(
            str(index_path), embeddings, allow_dangerous_deserialization=True
        )
    return None


def add_to_vectorstore(user_id: str, texts: List[str], metadatas: List[Dict]) -> FAISS:
    """Add documents to user's FAISS index."""
    embeddings = get_embeddings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )
    docs = []
    for text, meta in zip(texts, metadatas):
        chunks = splitter.create_documents([text], metadatas=[meta])
        docs.extend(chunks)

    index_path = VECTOR_STORE_PATH / user_id
    existing = get_vectorstore(user_id)

    if existing:
        existing.add_documents(docs)
        existing.save_local(str(index_path))
        return existing
    else:
        vs = FAISS.from_documents(docs, embeddings)
        vs.save_local(str(index_path))
        return vs


def extract_text_from_pdf(file_path: str) -> str:
    """Extract all text from a PDF file."""
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


RAG_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""You are NeuroLearn AI, a helpful academic learning assistant.
Use the context below to answer the student's question.
Be clear, concise, and explain step by step when needed.
If the context is not enough, answer from your own knowledge.

Context:
{context}

Student Question: {question}

Answer:""",
)


def query_rag(user_id: str, question: str, language: str = "en") -> Dict[str, Any]:
    """Main RAG query — retrieves relevant chunks then generates answer."""
    llm = get_llm()
    vs = get_vectorstore(user_id)

    # Language instruction
    lang_map = {"hi": "Hindi", "ta": "Tamil", "te": "Telugu", "bn": "Bengali"}
    lang_note = (
        f"\n\nImportant: Respond in {lang_map[language]}."
        if language in lang_map
        else ""
    )

    if vs:
        # Retrieve top 4 relevant chunks from uploaded notes
        retriever = vs.as_retriever(search_kwargs={"k": 4})
        retrieved = retriever.invoke(question)
        sources = list(
            {doc.metadata.get("source", "Uploaded notes") for doc in retrieved}
        )
        context = "\n\n".join([doc.page_content for doc in retrieved])
        confidence = min(len(retrieved) / 4.0, 1.0)

        prompt = RAG_PROMPT.format(context=context, question=question + lang_note)
    else:
        # No notes uploaded yet — answer from general knowledge
        sources = ["General knowledge"]
        confidence = 0.6
        prompt = f"""You are NeuroLearn AI, a helpful academic assistant.
Answer this academic question clearly and step by step.{lang_note}

Question: {question}

Answer:"""

    response = llm.invoke(prompt)
    answer = response.content if hasattr(response, "content") else str(response)

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
    }
