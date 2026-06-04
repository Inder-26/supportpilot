"""
tools/search_kb.py — Agent tool 2.

Queries the ChromaDB knowledge base for relevant FAQ/doc chunks
using semantic similarity search.

Returns: list of relevant text chunks
"""

from __future__ import annotations
import os

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

from logger import get_logger
from exceptions import (
    KnowledgeBaseError,
    KnowledgeBaseNotInitialisedError,
    NoRelevantChunksError,
)

load_dotenv()
logger = get_logger("tools.search_kb")

COLLECTION_NAME    = "supportpilot_kb"
TOP_K              = 3
SIMILARITY_THRESHOLD = 0.85   # ChromaDB distance — lower = more similar

_client: chromadb.Client | None = None
_collection = None


def _get_collection():
    """Lazy-initialise ChromaDB client and collection."""
    global _client, _collection
    if _collection is not None:
        return _collection

    db_path = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "chroma_db")
    logger.debug(f"Connecting to ChromaDB at {db_path}")

    try:
        _client = chromadb.PersistentClient(path=db_path)
        ef = embedding_functions.DefaultEmbeddingFunction()
        _collection = _client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
        )
        logger.info(f"ChromaDB collection loaded | count={_collection.count()}")
        return _collection
    except Exception as e:
        logger.error(f"Failed to load ChromaDB collection: {e}")
        raise KnowledgeBaseNotInitialisedError(
            "ChromaDB collection not found. Run knowledge_base/ingest.py first.",
            details={"error": str(e), "path": db_path}
        ) from e


def search_kb(query: str, category: str | None = None) -> list[str]:
    """
    Searches the knowledge base for chunks relevant to the query.

    Args:
        query:    natural language search query
        category: optional category filter (metadata filter)

    Returns:
        list of relevant text strings (up to TOP_K)

    Raises:
        KnowledgeBaseNotInitialisedError: if KB hasn't been ingested
        KnowledgeBaseError: on any ChromaDB failure
        NoRelevantChunksError: if nothing passes the similarity threshold
    """
    logger.info(f"Searching KB | query='{query[:80]}' category={category}")

    collection = _get_collection()

    where_filter = {"category": category} if category else None

    try:
        results = collection.query(
            query_texts=[query],
            n_results=TOP_K,
            where=where_filter,
            include=["documents", "distances"],
        )
    except Exception as e:
        logger.error(f"ChromaDB query failed: {e}")
        raise KnowledgeBaseError(
            f"ChromaDB query failed: {e}",
            details={"query": query}
        ) from e

    documents = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]

    # Filter by similarity threshold
    filtered = [
        doc for doc, dist in zip(documents, distances)
        if dist <= SIMILARITY_THRESHOLD
    ]

    if not filtered:
        logger.warning(
            f"No chunks above threshold | best_distance={min(distances) if distances else 'N/A'}"
        )
        raise NoRelevantChunksError(
            "No relevant KB chunks found for query",
            details={"query": query, "distances": distances}
        )

    logger.info(f"KB search returned {len(filtered)} chunks")
    return filtered
