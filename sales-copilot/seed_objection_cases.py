"""
GSM Sales Copilot — Qdrant Collection Setup + Seed 100 Cases

Run this ONCE after migration_objection_cases.sql is applied.
Creates Qdrant collection and indexes all 100 objection cases.

Usage:
  python seed_objection_cases.py

Requirements:
  - PostgreSQL with migration applied (objection_cases table exists)
  - Qdrant running on localhost:6333 (or set QDRANT_URL env)
  - sentence-transformers installed (pip install sentence-transformers)
  - psycopg2 or asyncpg installed
"""

import json
import os
import sys
import time
import uuid
import hashlib
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from sentence_transformers import SentenceTransformer

# ─── Configuration ──────────────────────────────────────────────
POSTGRES_DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://gsm:gsm@localhost:5432/gsm"
)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "sales_objections"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_SIZE = 384
BATCH_SIZE = 16

TENANT_SEED = "00000000-0000-0000-0000-000000000000"  # global seed cases

# ─── Step 1: Load embedding model ──────────────────────────────
print(f"Loading embedding model: {EMBEDDING_MODEL}")
model = SentenceTransformer(EMBEDDING_MODEL)
print(f"✓ Model loaded, vector size: {model.get_sentence_embedding_dimension()}")


# ─── Step 2: Create Qdrant collection ──────────────────────────
print(f"\nCreating Qdrant collection: {COLLECTION}")

# Delete if exists (idempotent re-run during development)
r = requests.delete(f"{QDRANT_URL}/collections/{COLLECTION}")
if r.status_code == 200:
    print(f"  Deleted existing collection")

# Create fresh
create_payload = {
    "vectors": {
        "size": VECTOR_SIZE,
        "distance": "Cosine"
    },
    "optimizers_config": {
        "default_segment_number": 2,
        "indexing_threshold": 10000
    },
    "on_disk_payload": True,
}
r = requests.put(
    f"{QDRANT_URL}/collections/{COLLECTION}",
    json=create_payload
)
r.raise_for_status()
print(f"  ✓ Collection created")

# Create payload indexes for fast filtering
INDEXES = [
    ("case_id", "keyword"),
    ("tenant_id", "keyword"),
    ("category", "keyword"),
    ("category_label", "keyword"),
    ("is_seed", "bool"),
    ("is_published", "bool"),
    ("car_brand", "keyword"),
    ("fluid_type", "keyword"),
    ("tags", "keyword"),
    ("usage_count", "integer"),
    ("quality_score", "float"),
]

for field, ftype in INDEXES:
    r = requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION}/index",
        json={"field_name": field, "field_schema": ftype}
    )
    if r.status_code == 200:
        print(f"  ✓ Index on '{field}' ({ftype})")
    else:
        print(f"  ⚠ Index on '{field}' failed: {r.text}")


# ─── Step 3: Connect to PostgreSQL ─────────────────────────────
print(f"\nConnecting to PostgreSQL: {POSTGRES_DSN.split('@')[-1]}")
conn = psycopg2.connect(POSTGRES_DSN)
conn.autocommit = False
cursor = conn.cursor(cursor_factory=RealDictCursor)


# ─── Step 4: Load all cases from PostgreSQL ────────────────────
print("\nLoading objection cases from PostgreSQL...")
cursor.execute("""
    SELECT id, tenant_id, number, category, category_label,
           objection_text, response_text, tags,
           content_hash, is_seed, is_published,
           car_brand, fluid_type
    FROM objection_cases
    WHERE is_published = true
    ORDER BY id
""")
cases = cursor.fetchall()
print(f"  ✓ Loaded {len(cases)} cases")

if not cases:
    print("  ⚠ No cases found. Did you run:")
    print("    psql -d gsm -f objection_cases.sql")
    sys.exit(1)


# ─── Step 5: Embed all objection texts in batches ─────────────
print(f"\nEmbedding {len(cases)} objection texts (batch size {BATCH_SIZE})...")
start_time = time.time()

vectors = []
for i in range(0, len(cases), BATCH_SIZE):
    batch = cases[i:i + BATCH_SIZE]
    texts = [c["objection_text"] for c in batch]
    batch_vectors = model.encode(
        texts,
        batch_size=len(batch),
        show_progress_bar=False,
        convert_to_numpy=True,
    ).tolist()
    vectors.extend(batch_vectors)
    print(f"  Embedded {min(i + BATCH_SIZE, len(cases))}/{len(cases)}")

elapsed = time.time() - start_time
print(f"  ✓ Done in {elapsed:.1f}s ({len(vectors) / elapsed:.1f} emb/s)")


# ─── Step 6: Upsert all points into Qdrant ────────────────────
print(f"\nUpserting {len(cases)} points to Qdrant...")

points = []
for case, vector in zip(cases, vectors):
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, case["id"]))
    points.append({
        "id": point_id,
        "vector": vector,
        "payload": {
            "case_id": case["id"],
            "tenant_id": str(case["tenant_id"]),
            "number": case["number"],
            "category": case["category"],
            "category_label": case["category_label"],
            "objection_text": case["objection_text"],
            "response_text": case["response_text"],
            "tags": case["tags"] or [],
            "content_hash": case["content_hash"],
            "is_seed": case["is_seed"],
            "is_published": case["is_published"],
            "car_brand": case["car_brand"],
            "fluid_type": case["fluid_type"],
            "usage_count": 0,
            "quality_score": 0.5,
        }
    })

# Upsert in batches
for i in range(0, len(points), BATCH_SIZE):
    batch = points[i:i + BATCH_SIZE]
    r = requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION}/points",
        json={"points": batch}
    )
    r.raise_for_status()
    print(f"  Upserted {min(i + BATCH_SIZE, len(points))}/{len(points)}")


# ─── Step 7: Update PostgreSQL with qdrant_point_id ───────────
print("\nLinking Qdrant point IDs back to PostgreSQL...")
for point in points:
    cursor.execute(
        """
        UPDATE objection_cases
        SET qdrant_point_id = %s::uuid
        WHERE id = %s
        """,
        (point["id"], point["payload"]["case_id"])
    )
conn.commit()
print(f"  ✓ Updated {len(points)} rows with qdrant_point_id")


# ─── Step 8: Verification test ────────────────────────────────
print("\n" + "=" * 60)
print("VERIFICATION TEST")
print("=" * 60)

test_queries = [
    ("У вас слишком дорого", "price"),
    ("Масло темнеет через неделю", "quality"),
    ("Срок поставки слишком долгий", "logistics"),
    ("О вас никто не слышал", "brand"),
    ("Нам ничего не нужно", "closing"),
]

for query, expected_cat in test_queries:
    query_vector = model.encode([query])[0].tolist()
    r = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
        json={
            "vector": query_vector,
            "limit": 3,
            "with_payload": True,
            "score_threshold": 0.3,
        }
    )
    r.raise_for_status()
    results = r.json()["result"]

    print(f"\n🔍 Query: '{query}'")
    print(f"   Expected category: {expected_cat}")
    for i, hit in enumerate(results, 1):
        score = hit["score"]
        cat = hit["payload"]["category"]
        cid = hit["payload"]["case_id"]
        obj = hit["payload"]["objection_text"][:60]
        marker = "✓" if cat == expected_cat else " "
        print(f"   {i}. {marker} [{score:.3f}] {cid}: {obj}... (cat={cat})")

print("\n" + "=" * 60)
print(f"✅ Done! {len(cases)} cases indexed in Qdrant collection '{COLLECTION}'")
print("=" * 60)
print(f"\nNext steps:")
print(f"  1. Start MCP server: npx tsx mcp-objection-server.ts")
print(f"  2. Test from LLM: search_objection_cases(objection='У вас дорого')")
print(f"  3. Integrate with /api/v1/sales/handle-objection endpoint")
