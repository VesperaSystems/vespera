from vespera.llm.ollama import model_matches


def test_exact_match():
    assert model_matches("qwen3:4b", ["qwen3:4b", "qwen3:8b"])


def test_untagged_matches_latest():
    assert model_matches("qwen3", ["qwen3:latest"])


def test_no_match():
    assert not model_matches("qwen3:4b", ["qwen3:8b"])
    assert not model_matches("qwen3:4b", [])


def test_tagged_does_not_match_latest():
    assert not model_matches("qwen3:4b", ["qwen3:latest"])
