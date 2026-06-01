from db.database import SessionLocal, create_tables
from core.weakness_engine import classify_mistake

create_tables()
db = SessionLocal()

print("=" * 50)
print("TESTING MISTAKE DNA CLASSIFIER")
print("=" * 50)

tests = [
    {
        "question": "What is the derivative of x²?",
        "student_answer": "2x + 1",
        "correct_answer": "2x",
        "expected_type": "careless",
    },
    {
        "question": "What is Newton's second law?",
        "student_answer": "Force equals mass divided by acceleration",
        "correct_answer": "Force equals mass times acceleration (F=ma)",
        "expected_type": "concept",
    },
    {
        "question": "Calculate 15% of 240",
        "student_answer": "34",
        "correct_answer": "36",
        "expected_type": "calculation",
    },
]

for t in tests:
    result = classify_mistake(t["question"], t["student_answer"], t["correct_answer"])
    match = "✅" if result["type"] == t["expected_type"] else "⚠️"
    print(f"\n{match} Question: {t['question']}")
    print(f"   Expected: {t['expected_type']}")
    print(f"   Got:      {result['type']}")
    print(f"   Reason:   {result['reason']}")

db.close()
print("\n✅ Weakness engine test complete!")
