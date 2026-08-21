import sys
from app.db.database import SessionLocal
from sqlalchemy import text
from sentence_transformers import SentenceTransformer

db = SessionLocal()
doc_id = "3def7b13-6d5b-4a7c-915b-da49fef9ddde"
    
chunks = db.execute(text("SELECT embedding_text FROM chunks WHERE document_id = :did"), {"did": doc_id}).fetchall()
model = SentenceTransformer("intfloat/multilingual-e5-base", device='cpu')
max_tokens = model.max_seq_length

lengths = []
over_limit = 0
for r in chunks:
    passage = f"passage: {r[0]}"
    tokens = model.tokenizer.encode(passage)
    length = len(tokens)
    lengths.append(length)
    if length > max_tokens:
        over_limit += 1

print(f"number of chunks: {len(lengths)}")
print(f"minimum tokens: {min(lengths)}")
print(f"average tokens: {sum(lengths)/len(lengths):.2f}")
print(f"maximum tokens: {max(lengths)}")
print(f"number over model limit: {over_limit}")
