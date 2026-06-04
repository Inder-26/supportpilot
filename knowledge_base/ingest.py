"""
knowledge_base/ingest.py — one-time script to load faqs.json into ChromaDB.

Run this before starting the server:
    python knowledge_base/ingest.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
from chromadb.utils import embedding_functions

from logger import get_logger
from exceptions import KnowledgeBaseError

logger = get_logger("knowledge_base.ingest")

FAQ_PATH        = Path(__file__).parent / "faqs.json"
DB_PATH         = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "supportpilot_kb"


def ingest() -> None:
    logger.info(f"Starting KB ingest | source={FAQ_PATH}")

    with open(FAQ_PATH, "r", encoding="utf-8") as f:
        faqs = json.load(f)

    logger.info(f"Loaded {len(faqs)} FAQ entries")

    try:
        client = chromadb.PersistentClient(path=str(DB_PATH))
        ef = embedding_functions.DefaultEmbeddingFunction()

        # Delete existing collection if rebuilding
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.info("Deleted existing collection for rebuild")
        except Exception:
            pass

        collection = client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
        )

        documents, ids, metadatas = [], [], []

        for faq in faqs:
            # Combine Q+A as the document for richer semantic matching
            doc_text = f"Q: {faq['question']}\nA: {faq['answer']}"
            documents.append(doc_text)
            ids.append(faq["id"])
            metadatas.append({"category": faq["category"], "question": faq["question"]})

        collection.add(documents=documents, ids=ids, metadatas=metadatas)

        logger.info(f"Ingested {collection.count()} documents into ChromaDB")
        print(f"\n✓ Knowledge base ready — {collection.count()} chunks indexed at {DB_PATH}\n")

    except Exception as e:
        logger.error(f"Ingest failed: {e}")
        raise KnowledgeBaseError(f"Ingest failed: {e}") from e


if __name__ == "__main__":
    ingest()
