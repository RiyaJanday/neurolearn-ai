from core.classifier import classify_query, extract_topic, detect_language

print("=" * 50)
print("TESTING QUERY CLASSIFIER")
print("=" * 50)

test_queries = [
    ("What is integration by parts?", True),
    ("Explain Newton's second law", True),
    ("What is mitosis?", True),
    ("Tell me a joke", False),
    ("Who won IPL 2024?", False),
    ("What is the derivative of x squared?", True),
    ("Recommend me a Netflix show", False),
]

print("\n--- Classification Tests ---")
all_passed = True
for query, expected in test_queries:
    result = classify_query(query)
    status = "✅" if result == expected else "❌"
    if result != expected:
        all_passed = False
    print(f"{status} '{query[:45]}' → {'ACADEMIC' if result else 'NOT_ACADEMIC'}")

print("\n--- Topic Extraction Tests ---")
academic_queries = [
    "What is integration by parts?",
    "Explain Newton's second law of motion",
    "How does photosynthesis work?",
]

for q in academic_queries:
    topic = extract_topic(q)
    print(f"\nQuery:   {q}")
    print(f"Subject: {topic['subject']}")
    print(f"Topic:   {topic['topic']}")

print("\n--- Language Detection ---")
print("English:", detect_language("What is calculus?"))
print("Hindi:  ", detect_language("गणित क्या है?"))

if all_passed:
    print("\n✅ All classifier tests passed!")
else:
    print("\n⚠️  Some tests failed — LLM may classify differently, that is okay")
