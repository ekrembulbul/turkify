"""Tier 3 — LLM rerank (opsiyonel, bağlamsal belirsizlik çözümü).

Yalnızca birden fazla geçerli aday bağlam gerektirdiğinde (ör. ``ask`` → ``ask``
/ ``aşk``) devreye girer. LLM **metin üretmez**, yalnızca verilen adaylardan
birini seçer; bu sayede anlam bozulmaz, kelime uydurulmaz.

Bir cümledeki tüm belirsiz kelimeler ``choose_batch`` ile TEK istekte
çözülür (kelime başına ayrı çağrı yerine); böylece çok belirsizli cümlelerde
gecikme düşer.

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
DEFAULT_MODEL = os.environ.get("TURKIFY_MODEL", "qwen3.5:9b")
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


# "1: secim" / "1. secim" / "1) secim" gibi satırları yakalar.
_BATCH_LINE_RE = re.compile(r"\s*(\d+)\s*[:.)\-]\s*(.+)")


def _build_batch_prompt(sentence: str, asks: tuple[tuple[str, tuple[str, ...]], ...]) -> str:
    items = "\n".join(
        f"{i}. {word} -> {', '.join(cands)}"
        for i, (word, cands) in enumerate(asks, start=1)
    )
    return _prompt_template().format(sentence=sentence, items=items)


def _parse_batch(
    response: str, asks: tuple[tuple[str, tuple[str, ...]], ...]
) -> tuple[str | None, ...]:
    """LLM toplu yanıtını her soru için seçilen adaya çözer.

    Yanıt "numara: secim" satırları içerir. Her soru indeksi için ilgili satırın
    seçimi adaylarla eşleştirilir; eşleşmezse o soru için ``None`` döner.
    """
    chosen: dict[int, str] = {}
    for line in response.splitlines():
        match = _BATCH_LINE_RE.match(line)
        if match:
            # İlk cevabı koru: model bazen yanıttan sonra uydurma ek görevler
            # üretip aynı numaraları tekrar yazıyor; bunlar gerçek cevabı ezmesin.
            chosen.setdefault(int(match.group(1)) - 1, match.group(2))
    return tuple(
        _match_candidate(chosen[i], cands) if i in chosen else None
        for i, (_word, cands) in enumerate(asks)
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


# Qwen3 vb. "düşünen" modellerin ürettiği reasoning bloğunu ve şablon özel
# tokenlarını yanıttan ayıklamak için desenler.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_OPEN_THINK_RE = re.compile(r"<think>.*", re.DOTALL | re.IGNORECASE)
_SPECIAL_TOKEN_RE = re.compile(r"<\|[^|]*\|>")

# 'think' parametresini desteklemeyen modeller için yeniden-deneme işareti.
_THINK_UNSUPPORTED = object()

# Çıktı uzunluğu sınırı: yalnızca "1: secim" gibi kısa yanıt gerekir. Reasoning
# sızsa bile üretimi keserek timeout'a takılmayı önler.
_NUM_PREDICT = 256


def _strip_thinking(text: str) -> str:
    """Yanıttan <think>...</think> bloğunu ve özel şablon tokenlarını temizler."""
    text = _THINK_RE.sub("", text)
    text = _OPEN_THINK_RE.sub("", text)  # kapanmamış (kesik) blok
    text = _SPECIAL_TOKEN_RE.sub("", text)
    return text.strip()


def _post_generate(prompt: str, model: str, timeout: float, *, think: bool | None):
    """Tek bir /api/generate isteği. ``think`` desteklenmiyorsa sentinel döner."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        # num_predict üretimi sınırlar (timeout koruması). 'stop' kullanmıyoruz:
        # model bazen önce boş şablon ("1:\n2:") yazıp gerçek cevabı blank satır
        # sonrası veriyor; "\n\n" stop'u bunu keserdi. Bunun yerine _parse_batch
        # boş satırları yok sayar ve her numaranın ilk DOLU cevabını alır.
        "options": {"temperature": 0, "num_predict": _NUM_PREDICT},
    }
    if think is not None:
        payload["think"] = think  # düşünen modellerde reasoning'i kapatır

    request = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = _http_detail(exc)
        if think is not None and "think" in str(detail).lower():
            return _THINK_UNSUPPORTED  # model 'think' parametresini bilmiyor
        if exc.code == 404:
            _log.warning(
                "[Tier3] Ollama: model %r bulunamadi (once: ollama pull %s)",
                model, model,
            )
        else:
            _log.warning("[Tier3] Ollama HTTP %s hatasi: %s", exc.code, detail)
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
        if think is not None and "think" in str(data["error"]).lower():
            return _THINK_UNSUPPORTED
        _log.warning("[Tier3] Ollama hatasi: %s", data["error"])
        return None
    return data.get("response")


def _query_ollama(prompt: str, model: str, timeout: float) -> str | None:
    # Önce reasoning kapalı dene ("düşünen" modellerde 60 sn takılmayı önler).
    result = _post_generate(prompt, model, timeout, think=False)
    if result is _THINK_UNSUPPORTED:
        # Model 'think' parametresini desteklemiyor → parametresiz tekrar dene.
        result = _post_generate(prompt, model, timeout, think=None)
    if isinstance(result, str):
        return _strip_thinking(result)
    return None


@lru_cache(maxsize=512)
def choose_batch(
    sentence: str,
    asks: tuple[tuple[str, tuple[str, ...]], ...],
    *,
    model: str = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[str | None, ...]:
    """Bir cümledeki tüm belirsiz kelimeleri TEK LLM isteğinde seçtirir.

    Kelime başına ayrı çağrı yerine, tüm cümle ve belirsiz kelimelerin adayları
    bir kez gönderilir; LLM her biri için seçim yapar. Bu, çok belirsizli
    cümlelerde gecikmeyi düşürür (N çağrı yerine 1).

    Args:
        sentence: Üzerinde çalışılan (Tier 1/2 uygulanmış) cümle.
        asks: ``(kelime, adaylar)`` ikilileri (hashlenebilir olması için tuple).
        model: Ollama model adı.
        timeout: İstek zaman aşımı (sn).

    Returns:
        ``asks`` ile aynı sırada seçimler; bir soru çözülemezse o öğe ``None``.
    """
    if not asks:
        return ()
    response = _query_ollama(_build_batch_prompt(sentence, asks), model, timeout)
    if response is None:
        return tuple(None for _ in asks)
    return _parse_batch(response, asks)
