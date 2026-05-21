"""Tier 3 batch LLM rerank testleri — Ollama HTTP çağrısı mock'lanır."""

import io
import logging
import urllib.error
import urllib.request

import pytest

from turkify import reranker


@pytest.fixture(autouse=True)
def clear_rerank_cache():
    reranker.choose_batch.cache_clear()
    yield
    reranker.choose_batch.cache_clear()


def _ask_one(word="ucu", cands=("ucu", "üçü")):
    return ((word, cands),)


# --- _match_candidate yardimcisi ---


def test_match_candidate_exact():
    assert reranker._match_candidate("aşk", ("ask", "aşk")) == "aşk"


def test_match_candidate_within_extra_text():
    assert reranker._match_candidate("Cevap: aşk", ("ask", "aşk")) == "aşk"


def test_match_candidate_prefers_longest_on_substring():
    assert reranker._match_candidate("aşk", ("aş", "aşk")) == "aşk"


def test_match_candidate_no_match_returns_none():
    assert reranker._match_candidate("xyz", ("ask", "aşk")) is None


# --- choose_batch ---


def test_empty_asks_returns_empty(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("bos asks'te sorgu yapilmamali")

    monkeypatch.setattr(reranker, "_query_ollama", fail)
    assert reranker.choose_batch("cumle", ()) == ()


def test_choose_batch_parses_single_selection(monkeypatch):
    monkeypatch.setattr(reranker, "_query_ollama", lambda *a, **k: "1: aşk")
    result = reranker.choose_batch("kalbimde ask var", (("ask", ("ask", "aşk")),))
    assert result == ("aşk",)


def test_choose_batch_parses_multiple_selections(monkeypatch):
    monkeypatch.setattr(reranker, "_query_ollama", lambda *a, **k: "1: ucu\n2: aşmak")
    asks = (("ucu", ("ucu", "uçu", "üçü")), ("asmak", ("asmak", "aşmak")))
    assert reranker.choose_batch("cumle", asks) == ("ucu", "aşmak")


def test_choose_batch_handles_various_separators(monkeypatch):
    monkeypatch.setattr(reranker, "_query_ollama", lambda *a, **k: "1) ucu\n2. aşmak")
    asks = (("ucu", ("ucu", "üçü")), ("asmak", ("asmak", "aşmak")))
    assert reranker.choose_batch("cumle", asks) == ("ucu", "aşmak")


def test_missing_selection_yields_none(monkeypatch):
    # Yanit sadece 1. soruyu cevapliyor; 2. soru None olmali.
    monkeypatch.setattr(reranker, "_query_ollama", lambda *a, **k: "1: ucu")
    asks = (("ucu", ("ucu", "üçü")), ("asmak", ("asmak", "aşmak")))
    assert reranker.choose_batch("cumle", asks) == ("ucu", None)


def test_invalid_selection_yields_none(monkeypatch):
    monkeypatch.setattr(reranker, "_query_ollama", lambda *a, **k: "1: bambaska")
    assert reranker.choose_batch("cumle", _ask_one()) == (None,)


def test_returns_all_none_when_ollama_unavailable(monkeypatch):
    monkeypatch.setattr(reranker, "_query_ollama", lambda *a, **k: None)
    asks = (("ucu", ("ucu", "üçü")), ("asmak", ("asmak", "aşmak")))
    assert reranker.choose_batch("cumle", asks) == (None, None)


# --- Ollama hata tanilari ---


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
        result = reranker.choose_batch("cumle", _ask_one(), model="yok:14b")
    assert result == (None,)
    assert any("bulunamadi" in r.getMessage() for r in caplog.records)


def test_ollama_unreachable_logs_warning(monkeypatch, caplog):
    def raise_conn(*args, **kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", raise_conn)
    with caplog.at_level(logging.WARNING, logger="turkify"):
        result = reranker.choose_batch("cumle", _ask_one())
    assert result == (None,)
    assert any("erisilemedi" in r.getMessage() for r in caplog.records)


def test_timeout_logs_distinct_warning(monkeypatch, caplog):
    def raise_timeout(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", raise_timeout)
    with caplog.at_level(logging.WARNING, logger="turkify"):
        result = reranker.choose_batch("cumle", _ask_one())
    assert result == (None,)
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "zaman asimi" in messages and "erisilemedi" not in messages
