from core.rag_engine import get_llm, query_rag

print("Testing Groq connection...")

llm = get_llm()

# Simple test
response = llm.invoke("What is Newton's second law? Answer in 2 sentences.")
print("\nGroq response:")
print(response.content)

# Full RAG test
print("\nTesting RAG query...")
result = query_rag(
    user_id="test-user-001",
    question="What is integration by parts?",
)
print("\nAnswer:", result["answer"][:300])
print("Sources:", result["sources"])
print("Confidence:", result["confidence"])

print("\n✅ Groq is working!")
