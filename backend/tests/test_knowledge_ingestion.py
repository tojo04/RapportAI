from pathlib import Path

from app.knowledge.ingestion import FakeEmbeddingProvider, chunk_document, corpus_revision, load_documents


def test_heading_chunks_are_deterministic(tmp_path: Path) -> None:
    (tmp_path / "product.md").write_text(
        "# Product\n\nIntro.\n\n## Feature\n\nStable text.\n", encoding="utf-8"
    )
    first = load_documents(tmp_path)
    second = load_documents(tmp_path)
    assert first == second
    assert chunk_document(first[0]) == chunk_document(second[0])
    assert [chunk.heading for chunk in chunk_document(first[0])] == ["Product", "Feature"]


def test_revision_changes_for_changes_and_deletions(tmp_path: Path) -> None:
    first_path = tmp_path / "one.md"
    second_path = tmp_path / "two.md"
    first_path.write_text("# One\n\nFirst", encoding="utf-8")
    second_path.write_text("# Two\n\nSecond", encoding="utf-8")
    original = corpus_revision(load_documents(tmp_path), "fake", 4)
    first_path.write_text("# One\n\nChanged", encoding="utf-8")
    changed = corpus_revision(load_documents(tmp_path), "fake", 4)
    second_path.unlink()
    deleted = corpus_revision(load_documents(tmp_path), "fake", 4)
    assert original != changed != deleted


def test_revision_never_mixes_model_or_dimensions(tmp_path: Path) -> None:
    (tmp_path / "one.md").write_text("# One\n\nFirst", encoding="utf-8")
    documents = load_documents(tmp_path)
    assert corpus_revision(documents, "model-a", 4) != corpus_revision(documents, "model-b", 4)
    assert corpus_revision(documents, "model-a", 4) != corpus_revision(documents, "model-a", 8)


def test_fake_embeddings_are_reproducible_and_dimensioned() -> None:
    provider = FakeEmbeddingProvider(dimensions=8)
    first = provider.embed(["same", "different"])
    assert first == provider.embed(["same", "different"])
    assert len(first[0]) == 8
    assert first[0] != first[1]
