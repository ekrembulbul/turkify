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
import os
import re
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)

OLLAMA_HOST = "http://localhost:11434"
# Varsayılan model TURKIFY_MODEL ortam değişkeniyle değiştirilebilir; CLI'deki
# --model bayrağı bunu da geçersiz kılar (bkz. __main__).
DEFAULT_MODEL = os.environ.get("TURKIFY_MODEL", "qwen2.5:7b")
DEFAULT_TIMEOUT = 10.0

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
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
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
