import pytest
from rag import RAG


@pytest.mark.unit
def test_rag_retrieves_relevant_context(tmp_path):
    (tmp_path / "a.md").write_text("We provide marketing services for dental clinics.")
    (tmp_path / "b.md").write_text("Emergency plumbing and drain repair.")

    rag = RAG(knowledge_dir=str(tmp_path))
    results = rag.retrieve("dental marketing growth")

    assert results
    joined = "\n".join(results).lower()
    assert "dental" in joined
    assert "marketing" in joined
