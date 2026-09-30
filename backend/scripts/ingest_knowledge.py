import argparse
from pathlib import Path

from app.core.config import get_settings
from app.knowledge.ingestion import FakeEmbeddingProvider, KnowledgeIngester, OpenAIEmbeddingProvider
from app.storage.database import create_database_engine, create_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a versioned RapportAI knowledge corpus.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fake", action="store_true", help="Use deterministic, non-semantic test vectors.")
    mode.add_argument("--real", action="store_true", help="Call the configured OpenAI embeddings API (billable).")
    parser.add_argument("--path", type=Path, default=Path(__file__).parents[1] / "knowledge")
    args = parser.parse_args()
    settings = get_settings()
    if args.real:
        if not settings.openai_api_key:
            parser.error("OPENAI_API_KEY is required with --real")
        provider = OpenAIEmbeddingProvider(
            settings.openai_api_key,
            settings.knowledge_embedding_model,
            settings.knowledge_embedding_dimensions,
        )
    else:
        provider = FakeEmbeddingProvider()
    ingester = KnowledgeIngester(
        create_session_factory(create_database_engine(settings.database_url)), provider
    )
    result = ingester.ingest(args.path)
    print(
        f"Published {result.corpus_revision[:12]}: {result.document_count} documents, "
        f"{result.chunk_count} chunks, {result.embedded_count} embedded, {result.reused_count} reused."
    )


if __name__ == "__main__":
    main()
