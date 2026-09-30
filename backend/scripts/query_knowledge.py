import argparse

from app.core.config import get_settings
from app.knowledge.ingestion import FakeEmbeddingProvider, OpenAIEmbeddingProvider
from app.knowledge.retrieval import PostgresSearchBackend, RetrievalService
from app.storage.database import create_database_engine, create_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect active RapportAI knowledge retrieval.")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=4)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fake", action="store_true", help="Use fake vectors; only valid for a fake corpus.")
    mode.add_argument("--real", action="store_true", help="Use billable OpenAI embeddings.")
    args = parser.parse_args()
    settings = get_settings()
    if args.real:
        if not settings.openai_api_key:
            parser.error("OPENAI_API_KEY is required with --real")
        provider = OpenAIEmbeddingProvider(settings.openai_api_key, settings.knowledge_embedding_model, settings.knowledge_embedding_dimensions)
    else:
        provider = FakeEmbeddingProvider()
    sessions = create_session_factory(create_database_engine(settings.database_url))
    result = RetrievalService(
        PostgresSearchBackend(sessions), provider, settings.knowledge_evidence_threshold
    ).retrieve(args.query, args.top_k)
    if not result.evidence:
        print(result.reason)
    for item in result.evidence:
        print(f"{item.distance:.4f} {item.chunk_id[:12]} {item.source_path}#{item.heading}\n{item.text}\n")


if __name__ == "__main__":
    main()
