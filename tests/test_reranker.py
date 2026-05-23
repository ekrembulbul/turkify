"""Tier 3 batch LLM rerank testleri — OpenAI-uyumlu HTTP çağrısı mock'lanır."""

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


def _openai_payload(content: str) -> dict:
    """OpenAI-uyumlu /chat/completions başarı yanıtı (asistan içeriği)."""
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


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

    monkeypatch.setattr(reranker, "_chat_completion", fail)
    assert reranker.choose_batch("cumle", ()) == ()


def test_choose_batch_parses_single_selection(monkeypatch):
    monkeypatch.setattr(reranker, "_chat_completion", lambda *a, **k: "1: aşk")
    result = reranker.choose_batch("kalbimde ask var", (("ask", ("ask", "aşk")),))
    assert result == ("aşk",)


def test_choose_batch_parses_multiple_selections(monkeypatch):
    monkeypatch.setattr(reranker, "_chat_completion", lambda *a, **k: "1: ucu\n2: aşmak")
    asks = (("ucu", ("ucu", "uçu", "üçü")), ("asmak", ("asmak", "aşmak")))
    assert reranker.choose_batch("cumle", asks) == ("ucu", "aşmak")


def test_choose_batch_handles_various_separators(monkeypatch):
    monkeypatch.setattr(reranker, "_chat_completion", lambda *a, **k: "1) ucu\n2. aşmak")
    asks = (("ucu", ("ucu", "üçü")), ("asmak", ("asmak", "aşmak")))
    assert reranker.choose_batch("cumle", asks) == ("ucu", "aşmak")


def test_parse_batch_ignores_trailing_hallucination(monkeypatch):
    # Model cevaptan sonra uydurma ek gorevler uretirse, ilk cevaplar korunmali.
    response = "1: turu\n2: işe\n\nHere is the task:\n1: adamı\n2: bulmak"
    monkeypatch.setattr(reranker, "_chat_completion", lambda *a, **k: response)
    asks = (("turu", ("turu", "türü")), ("ise", ("ise", "işe")))
    assert reranker.choose_batch("cumle", asks) == ("turu", "işe")


def test_parse_batch_ignores_empty_scaffold(monkeypatch):
    # Model once bos sablon ("1:\n2:") yazip sonra gercek cevaplari verebilir.
    response = "1:\n2:\n\n1: doküman\n2: sor"
    monkeypatch.setattr(reranker, "_chat_completion", lambda *a, **k: response)
    asks = (("dokuman", ("dokuman", "doküman")), ("sor", ("sor", "şor")))
    assert reranker.choose_batch("cumle", asks) == ("doküman", "sor")


def test_missing_selection_yields_none(monkeypatch):
    # Yanit sadece 1. soruyu cevapliyor; 2. soru None olmali.
    monkeypatch.setattr(reranker, "_chat_completion", lambda *a, **k: "1: ucu")
    asks = (("ucu", ("ucu", "üçü")), ("asmak", ("asmak", "aşmak")))
    assert reranker.choose_batch("cumle", asks) == ("ucu", None)


def test_invalid_selection_yields_none(monkeypatch):
    monkeypatch.setattr(reranker, "_chat_completion", lambda *a, **k: "1: bambaska")
    assert reranker.choose_batch("cumle", _ask_one()) == (None,)


def test_returns_all_none_when_ollama_unavailable(monkeypatch):
    monkeypatch.setattr(reranker, "_chat_completion", lambda *a, **k: None)
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
    payload = _openai_payload("<think>cok uzun reasoning</think>\n1: aşk")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _FakeResponse(payload))
    result = reranker.choose_batch("kalbimde ask var", (("ask", ("ask", "aşk")),))
    assert result == ("aşk",)


# --- OpenAI-uyumlu transport (gercek urlopen mock'lanir) ---


def test_request_hits_chat_completions_with_messages(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["headers"] = request.headers
        return _FakeResponse(_openai_payload("1: aşk"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = reranker.choose_batch("kalbimde ask var", (("ask", ("ask", "aşk")),))
    assert result == ("aşk",)
    assert captured["url"].endswith("/chat/completions")
    assert captured["body"]["messages"][0]["role"] == "user"
    assert captured["body"]["temperature"] == 0


def test_llm_options_merged_into_payload(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(_openai_payload("1: aşk"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        reranker,
        "LLM_OPTIONS",
        {"chat_template_kwargs": {"enable_thinking": False}, "temperature": 0.5},
    )
    reranker.choose_batch("kalbimde ask var", (("ask", ("ask", "aşk")),))
    body = captured["body"]
    # Kullanici alani eklenir; temperature ezilebilir.
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["temperature"] == 0.5
    # Cekirdek alanlar (model/messages/stream) kullanici tarafindan bozulamaz.
    assert body["messages"][0]["content"]
    assert body["stream"] is False


def test_llm_options_cannot_clobber_messages(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(_openai_payload("1: aşk"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(reranker, "LLM_OPTIONS", {"messages": [], "stream": True})
    reranker.choose_batch("kalbimde ask var", (("ask", ("ask", "aşk")),))
    assert captured["body"]["messages"] != []      # bizim prompt korunur
    assert captured["body"]["stream"] is False      # stream zorla False


def test_assistant_prefill_appended_when_set(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(_openai_payload("1: aşk"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(reranker, "ASSISTANT_PREFILL", "<think>\n\n</think>\n\n")
    reranker.choose_batch("kalbimde ask var", (("ask", ("ask", "aşk")),))
    messages = captured["body"]["messages"]
    assert messages[0]["role"] == "user"
    assert messages[-1] == {"role": "assistant", "content": "<think>\n\n</think>\n\n"}


def test_no_assistant_prefill_by_default(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(_openai_payload("1: aşk"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(reranker, "ASSISTANT_PREFILL", None)
    reranker.choose_batch("kalbimde ask var", (("ask", ("ask", "aşk")),))
    roles = [m["role"] for m in captured["body"]["messages"]]
    assert roles == ["user"]  # prefill yok


def test_api_key_adds_authorization_header(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["headers"] = {k.lower(): v for k, v in request.headers.items()}
        return _FakeResponse(_openai_payload("1: aşk"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(reranker, "API_KEY", "gizli-anahtar")
    reranker.choose_batch("kalbimde ask var", (("ask", ("ask", "aşk")),))
    assert captured["headers"].get("authorization") == "Bearer gizli-anahtar"


def test_unexpected_response_shape_yields_none(monkeypatch, caplog):
    # "choices" yoksa (beklenmeyen bicim) icerik cikarilamaz -> None.
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: _FakeResponse({"unexpected": True})
    )
    with caplog.at_level(logging.WARNING, logger="turkify"):
        result = reranker.choose_batch("cumle", _ask_one())
    assert result == (None,)
    assert any("icerik yok" in r.getMessage() for r in caplog.records)


# --- Hata tanilari ---


def test_missing_model_logs_clear_warning(monkeypatch, caplog):
    def raise_404(*args, **kwargs):
        raise urllib.error.HTTPError(
            "http://localhost:11434/v1/chat/completions",
            404,
            "Not Found",
            {},
            io.BytesIO(b'{"error":{"message":"model not found"}}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", raise_404)
    with caplog.at_level(logging.WARNING, logger="turkify"):
        result = reranker.choose_batch("cumle", _ask_one(), model="yok:14b")
    assert result == (None,)
    assert any("bulunamadi" in r.getMessage() for r in caplog.records)


def test_auth_error_logs_warning(monkeypatch, caplog):
    def raise_401(*args, **kwargs):
        raise urllib.error.HTTPError(
            "http://localhost:11434/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":{"message":"invalid api key"}}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", raise_401)
    with caplog.at_level(logging.WARNING, logger="turkify"):
        result = reranker.choose_batch("cumle", _ask_one())
    assert result == (None,)
    assert any("Yetkilendirme" in r.getMessage() for r in caplog.records)


def test_server_unreachable_logs_warning(monkeypatch, caplog):
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
