"""Tier 3 — LLM rerank (opsiyonel, bağlamsal belirsizlik çözümü).

Yalnızca birden fazla geçerli aday bağlam gerektirdiğinde (ör. ``ask`` → ``ask``
/ ``aşk``) devreye girer. LLM **metin üretmez**, yalnızca verilen adaylardan
birini seçer; bu sayede anlam bozulmaz, kelime uydurulmaz.

Ollama'nın yerel HTTP API'sini standart kütüphane (``urllib``) ile kullanır;
ekstra çalışma zamanı bağımlılığı eklemez. Ollama erişilemezse veya yanıt
adaylardan biri değilse ``None`` döner ve çağıran taraf güvenli tarafta
(deterministik karar) kalır.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

# Tanı mesajları "turkify" günlüğüne yazılır. Bunlar WARNING seviyesindedir;
# böylece --verbose olmasa bile (kullanıcı --llm/--model'i bilerek istediği için)
# stderr'de görünür, stdout temiz kalır.
_log = logging.getLogger("turkify")

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)

OLLAMA_HOST = "http://localhost:11434"
# Varsayılan model TURKIFY_MODEL ortam değişkeniyle değiştirilebilir; CLI'deki
# --model bayrağı bunu da geçersiz kılar (bkz. __main__).
DEFAULT_MODEL = os.environ.get("TURKIFY_MODEL", "qwen2.5:7b")
# Büyük modeller ilk çağrıda belleğe yüklenirken (cold start) yavaş olabilir;
# bu yüzden cömert bir varsayılan. Ollama kapalıysa bağlantı zaten anında
# reddedilir, bu süre yalnızca "açık ama yavaş" durumunda beklenir.
# TURKIFY_TIMEOUT ortam değişkeniyle ayarlanabilir.
DEFAULT_TIMEOUT = float(os.environ.get("TURKIFY_TIMEOUT", "60"))

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "rerank_prompt.txt"


@lru_cache(maxsize=1)
def _prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def available(*, timeout: float = 2.0) -> bool:
    """Ollama yerel sunucusu erişilebilir mi?"""
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _build_prompt(sentence: str, word: str, candidates: tuple[str, ...]) -> str:
    return _prompt_template().format(
        sentence=sentence,
        word=word,
        candidates=", ".join(candidates),
    )


def _match_candidate(answer: str, candidates: tuple[str, ...]) -> str | None:
    """LLM yanıtını adaylardan biriyle eşler; eşleşme yoksa ``None``.

    Önce tam eşleşme denenir. Yanıt fazladan metin içeriyorsa, yanıttaki
    **tam kelimeler** (alt-dizge değil) adaylarla karşılaştırılır; böylece
    ör. ``bambaska`` yanıtı ``ask`` adayıyla yanlışlıkla eşleşmez.
    """
    answer = answer.strip()
    for candidate in candidates:
        if answer == candidate:
            return candidate
    tokens = set(_WORD_RE.findall(answer))
    for candidate in sorted(candidates, key=len, reverse=True):
        if candidate in tokens:
            return candidate
    return None


def _http_detail(exc: urllib.error.HTTPError) -> str:
    """HTTP hata gövdesinden Ollama'nın 'error' mesajını çıkarır."""
    try:
        body = exc.read().decode("utf-8")
        return json.loads(body).get("error", body)
    except Exception:
        return str(exc)


def _query_ollama(prompt: str, model: str, timeout: float) -> str | None:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            _log.warning(
                "[Tier3] Ollama: model %r bulunamadi (once: ollama pull %s)",
                model, model,
            )
        else:
            _log.warning(
                "[Tier3] Ollama HTTP %s hatasi: %s", exc.code, _http_detail(exc)
            )
        return None
    except TimeoutError:
        # TimeoutError, OSError'in alt sinifidir; aşağıdaki bloktan ÖNCE yakalanmalı.
        _log.warning(
            "[Tier3] Ollama zaman asimi (%.0f sn). Model yukleniyor olabilir; "
            "tekrar deneyin veya TURKIFY_TIMEOUT'u artirin.",
            timeout,
        )
        return None
    except (urllib.error.URLError, OSError) as exc:
        _log.warning(
            "[Tier3] Ollama'ya erisilemedi (calisiyor mu? 'ollama serve'): %s", exc
        )
        return None
    except json.JSONDecodeError:
        _log.warning("[Tier3] Ollama yaniti cozulemedi (gecersiz JSON)")
        return None

    if data.get("error"):
        _log.warning("[Tier3] Ollama hatasi: %s", data["error"])
        return None
    return data.get("response")


@lru_cache(maxsize=2048)
def choose(
    sentence: str,
    word: str,
    candidates: tuple[str, ...],
    *,
    model: str = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT,
) -> str | None:
    """Adaylar arasından bağlama en uygun olanı LLM ile seçer.

    Args:
        sentence: Kelimenin geçtiği (üzerinde çalışılan) cümle.
        word: Düzeltilecek özgün (ASCII) kelime.
        candidates: Geçerli adaylar (hashlenebilir olması için ``tuple``).
        model: Ollama model adı.
        timeout: İstek zaman aşımı (sn).

    Returns:
        Seçilen aday; LLM erişilemez veya yanıt adaylardan biri değilse ``None``.
    """
    if len(candidates) < 2:
        return candidates[0] if candidates else None
    response = _query_ollama(_build_prompt(sentence, word, candidates), model, timeout)
    if response is None:
        return None
    return _match_candidate(response, candidates)
