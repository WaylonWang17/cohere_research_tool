import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Mock external API clients before importing research_tool,
# so no real network calls are made on import.
# test harness
mock_cohere = MagicMock()
mock_exa_module = MagicMock()
mock_wiki_module = MagicMock()
mock_dotenv = MagicMock()

sys.modules["cohere"] = mock_cohere
sys.modules["exa_py"] = mock_exa_module
sys.modules["wikipediaapi"] = mock_wiki_module
sys.modules["dotenv"] = mock_dotenv
sys.modules["cohere.types"] = MagicMock()

import research_tool

'''
ai generated unit tests
'''
# --- save_notes ---

def test_save_notes_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = research_tool.save_notes("test.md", "some content")
    assert result == [{"status": "saved", "path": os.path.join("notes", "test.md")}]
    assert (tmp_path / "notes" / "test.md").exists()

def test_save_notes_file_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    research_tool.question = "What is the capital of France?"
    research_tool.save_notes("france.md", "Paris is the capital.")
    content = (tmp_path / "notes" / "france.md").read_text(encoding="utf-8")
    assert "What is the capital of France?" in content
    assert "Paris is the capital." in content

def test_save_notes_strips_path_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = research_tool.save_notes("../../evil.md", "bad content")
    # should be written inside notes/, not two directories up
    assert (tmp_path / "notes" / "evil.md").exists()


# --- exa_func ---

def make_exa_result(title, highlights):
    r = MagicMock()
    r.url = f"https://example.com/{title}"
    r.title = title
    r.highlights = highlights
    return r

def make_rerank_item(index, score):
    item = MagicMock()
    item.index = index
    item.relevance_score = score
    return item

def test_exa_func_returns_top_reranked_results():
    raw = [
        make_exa_result("Alpha", ["alpha highlight"]),
        make_exa_result("Beta", ["beta highlight"]),
        make_exa_result("Gamma", ["gamma highlight"]),
    ]
    research_tool.exa.search.return_value.results = raw

    # rerank says: Gamma (index 2) is best, then Alpha (index 0)
    rerank_resp = MagicMock()
    rerank_resp.results = [make_rerank_item(2, 0.95), make_rerank_item(0, 0.80)]
    research_tool.co.rerank.return_value = rerank_resp

    results = research_tool.exa_func("test query")

    assert len(results) == 2
    assert results[0]["title"] == "Gamma"
    assert results[0]["relevance_score"] == 0.95
    assert results[1]["title"] == "Alpha"
    assert results[1]["relevance_score"] == 0.80

def test_exa_func_empty_results_skips_rerank():
    research_tool.exa.search.return_value.results = []
    research_tool.co.rerank.reset_mock()

    results = research_tool.exa_func("test query")

    assert results == []
    research_tool.co.rerank.assert_not_called()


# --- wikipedia_search ---

def make_wiki_page(title, summary, url):
    page = MagicMock()
    page.title = title
    page.summary = summary
    page.fullurl = url
    return page

def test_wikipedia_search_returns_best_page():
    page_a = make_wiki_page("Paris", "Paris is the capital of France.", "https://en.wikipedia.org/wiki/Paris")
    page_b = make_wiki_page("Paris, Texas", "A city in the US.", "https://en.wikipedia.org/wiki/Paris,_Texas")

    search_result = MagicMock()
    search_result.pages = {"Paris": page_a, "Paris, Texas": page_b}
    research_tool.wiki.search.return_value = search_result

    rerank_resp = MagicMock()
    rerank_resp.results = [make_rerank_item(0, 0.99)]  # picks page_a
    research_tool.co.rerank.return_value = rerank_resp

    results = research_tool.wikipedia_search("capital of France")

    assert len(results) == 1
    assert results[0]["title"] == "Paris"
    assert results[0]["url"] == "https://en.wikipedia.org/wiki/Paris"
    assert results[0]["relevance_score"] == 0.99

def test_wikipedia_search_no_pages_returns_error():
    search_result = MagicMock()
    search_result.pages = {}
    research_tool.wiki.search.return_value = search_result

    results = research_tool.wikipedia_search("xyzzy nonsense query")

    assert results == [{"error": "No wikipedia page found for xyzzy nonsense query"}]
