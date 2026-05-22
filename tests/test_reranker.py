"""Tier 3 batch LLM rerank testleri — Ollama HTTP çağrısı mock'lanır."""

import io
import json
import logging
import urllib.error
import urllib.request

import pytest

from turkify import reranker


class _FakeResponse:
    """urlopen için sahte bağlam yöneticisi (başarılı yanıt)."""

    status = 200

    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


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


def test_parse_batch_ignores_trailing_hallucination(monkeypatch):
    # Model cevaptan sonra uydurma ek gorevler uretirse, ilk cevaplar korunmali.
    response = "1: turu\n2: işe\n\nHere is the task:\n1: adamı\n2: bulmak"
    monkeypatch.setattr(reranker, "_query_ollama", lambda *a, **k: response)
    asks = (("turu", ("turu", "türü")), ("ise", ("ise", "işe")))
    assert reranker.choose_batch("cumle", asks) == ("turu", "işe")


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


# --- "düşünen" model yaniti (reasoning blogu) ---


def test_strip_thinking_removes_block_and_special_tokens():
    text = "<think>uzun uzun dusunuyorum...</think>\n1: aşk<|im_start|>"
    assert reranker._strip_thinking(text) == "1: aşk"


def test_strip_thinking_removes_unclosed_block():
    # num_predict ile kesilmis (kapanmamis) <think> tum kalani temizlemeli.
    text = "1: aşk\n<think>kesik dusunce sonsuza dek"
    assert reranker._strip_thinking(text) == "1: aşk"


def test_choose_batch_strips_thinking_before_parsing(monkeypatch):
    payload = {"response": "<think>cok uzun reasoning</think>\n1: aşk"}
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _FakeResponse(payload))
    result = reranker.choose_batch("kalbimde ask var", (("ask", ("ask", "aşk")),))
    assert result == ("aşk",)


def test_unsupported_think_param_falls_back(monkeypatch):
    # Ilk istek (think=False) "think" hatasi verir; parametresiz tekrar denenir.
    calls = []

    def fake_urlopen(request, timeout=None):
        body = json.loads(request.data.decode("utf-8"))
        calls.append("think" in body)
        if "think" in body:
            raise urllib.error.HTTPError(
                request.full_url, 400, "Bad Request", {},
                io.BytesIO(b'{"error":"this model does not support think"}'),
            )
        return _FakeResponse({"response": "1: aşk"})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = reranker.choose_batch("cumle", (("ask", ("ask", "aşk")),))
    assert result == ("aşk",)
    assert calls == [True, False]  # once think'li, sonra think'siz


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
