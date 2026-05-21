"""Tier 3 LLM rerank testleri — Ollama HTTP çağrısı mock'lanır."""

import io
import logging
import urllib.error
import urllib.request

import pytest

from turkify import reranker


@pytest.fixture(autouse=True)
def clear_rerank_cache():
    reranker.choose.cache_clear()
    yield
    reranker.choose.cache_clear()


def test_match_candidate_exact():
    assert reranker._match_candidate("aşk", ("ask", "aşk")) == "aşk"


def test_match_candidate_within_extra_text():
    # LLM bazen fazladan metin dondurur; aday icinden bulunmali.
    assert reranker._match_candidate("Cevap: aşk", ("ask", "aşk")) == "aşk"


def test_match_candidate_prefers_longest_on_substring():
    # "aş" ve "aşk" ikisi de aday olsa, daha uzun olan tercih edilir.
    assert reranker._match_candidate("aşk", ("aş", "aşk")) == "aşk"


def test_match_candidate_no_match_returns_none():
    assert reranker._match_candidate("xyz", ("ask", "aşk")) is None


def test_choose_single_candidate_returns_it_without_query(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("tek adayda LLM cagrilmamali")

    monkeypatch.setattr(reranker, "_query_ollama", fail)
    assert reranker.choose("cumle", "ask", ("aşk",)) == "aşk"


def test_choose_returns_llm_selection(monkeypatch):
    monkeypatch.setattr(reranker, "_query_ollama", lambda *a, **k: "aşk")
    assert reranker.choose("kalbimde ask var", "ask", ("ask", "aşk")) == "aşk"


def test_choose_returns_none_when_ollama_unavailable(monkeypatch):
    monkeypatch.setattr(reranker, "_query_ollama", lambda *a, **k: None)
    assert reranker.choose("cumle", "ask", ("ask", "aşk")) is None


def test_choose_returns_none_when_llm_answer_invalid(monkeypatch):
    monkeypatch.setattr(reranker, "_query_ollama", lambda *a, **k: "bambaska")
    assert reranker.choose("cumle", "ask", ("ask", "aşk")) is None


def test_missing_model_logs_clear_warning(monkeypatch, caplog):
    def raise_404(*args, **kwargs):
        raise urllib.error.HTTPError(
            "http://localhost:11434/api/generate",
            404,
            "Not Found",
            {},
            io.BytesIO(b'{"error":"model not found"}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", raise_404)
    with caplog.at_level(logging.WARNING, logger="turkify"):
        result = reranker.choose("cumle", "ucu", ("ucu", "üçü"), model="yok:14b")
    assert result is None
    assert any("bulunamadi" in r.getMessage() for r in caplog.records)


def test_ollama_unreachable_logs_warning(monkeypatch, caplog):
    def raise_conn(*args, **kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", raise_conn)
    with caplog.at_level(logging.WARNING, logger="turkify"):
        result = reranker.choose("cumle", "ucu", ("ucu", "üçü"))
    assert result is None
    assert any("erisilemedi" in r.getMessage() for r in caplog.records)


def test_timeout_logs_distinct_warning(monkeypatch, caplog):
    def raise_timeout(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", raise_timeout)
    with caplog.at_level(logging.WARNING, logger="turkify"):
        result = reranker.choose("cumle", "ucu", ("ucu", "üçü"))
    assert result is None
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "zaman asimi" in messages and "erisilemedi" not in messages
