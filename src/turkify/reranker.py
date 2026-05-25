"""Tier 3 — LLM rerank (opsiyonel, bağlamsal belirsizlik çözümü).

Yalnızca birden fazla geçerli aday bağlam gerektirdiğinde (ör. ``ask`` → ``ask``
/ ``aşk``) devreye girer. LLM **metin üretmez**, yalnızca verilen adaylardan
birini seçer; bu sayede anlam bozulmaz, kelime uydurulmaz.

Bir cümledeki tüm belirsiz kelimeler ``choose_batch`` ile TEK istekte
çözülür (kelime başına ayrı çağrı yerine); böylece çok belirsizli cümlelerde
gecikme düşer.

**OpenAI-uyumlu** yerel bir LLM sunucusunun ``/v1/chat/completions`` ucunu
standart kütüphane (``urllib``) ile kullanır; ekstra çalışma zamanı bağımlılığı
eklemez. Bu protokolü Ollama, LM Studio, llama.cpp (server), Jan, GPT4All, vLLM,
MLX (``mlx_lm.server``) gibi araçların hepsi konuştuğu için tek bir istemci
hepsini kapsar. Adres ``base_url`` ile seçilir (varsayılan: Ollama'nın yerel
OpenAI-uyumlu ucu). Sunucuya erişilemezse veya yanıt adaylardan biri değilse
``None`` döner ve çağıran taraf güvenli tarafta (deterministik karar) kalır.
"""

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from functools import lru_cache

from turkify import resources

# Tanı mesajları "turkify" günlüğüne yazılır. Bunlar WARNING seviyesindedir;
# böylece --verbose olmasa bile (kullanıcı --llm/--model'i bilerek istediği için)
# stderr'de görünür, stdout temiz kalır.
_log = logging.getLogger("turkify")

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)

# OpenAI-uyumlu API kök adresi. Sonuna "/chat/completions" ve "/models" eklenir.
# Varsayılan, Ollama'nın yerel OpenAI-uyumlu ucudur; LM Studio için ör.
# "http://localhost:1234/v1". TURKIFY_BASE_URL ile veya config (base_url) ile
# değiştirilir.
BASE_URL = os.environ.get("TURKIFY_BASE_URL", "http://localhost:11434/v1")
# Model zorunludur ve yapılandırmadan gelir (config "model" / CLI --model /
# TURKIFY_MODEL env). Hiçbiri verilmezse model None'dur ve Tier 3 (LLM) çalışmaz;
# otomatik model tespiti yapılmaz. Yerleşik bir varsayılan model YOKTUR.
DEFAULT_MODEL = os.environ.get("TURKIFY_MODEL")
# Büyük modeller ilk çağrıda belleğe yüklenirken (cold start) yavaş olabilir;
# bu yüzden cömert bir varsayılan. Sunucu kapalıysa bağlantı zaten anında
# reddedilir, bu süre yalnızca "açık ama yavaş" durumunda beklenir.
# TURKIFY_TIMEOUT ortam değişkeniyle ayarlanabilir.
DEFAULT_TIMEOUT = float(os.environ.get("TURKIFY_TIMEOUT", "60"))
# Yerel sunucular genelde anahtar istemez; bazıları (ör. vLLM) isteyebilir.
# Verilirse "Authorization: Bearer ..." başlığı eklenir. TURKIFY_API_KEY env'i
# veya config (api_key) ile ayarlanır.
API_KEY = os.environ.get("TURKIFY_API_KEY")
# /chat/completions gövdesine eklenecek sunucu/model-özel istek seçenekleri
# (config "llm_options"). OpenAI-uyumlu protokolde reasoning'i kapatma gibi
# ayarlar standart değildir; kullanıcı kendi sunucusunun beklediği alanı buraya
# yazar (ör. {"chat_template_kwargs": {"enable_thinking": false}}). temperature/
# max_tokens da buradan ezilebilir; model/messages/stream korunur.
LLM_OPTIONS: dict = {}
# İstek mesajlarının sonuna eklenecek bir asistan "prefill"i (config
# "assistant_prefill"). Boş/None ise eklenmez. Başlıca kullanım: "düşünen"
# modellerde reasoning'i atlatmak — değer ``<think>\n\n</think>\n\n`` verilirse
# model "zaten düşündüm (boş)" sayıp doğrudan cevaba geçer (Qwen'in kendi
# non-thinking mekanizması). Reasoning'i istek parametresiyle (chat_template_kwargs)
# kapatamayan motorlarda (ör. LM Studio MLX) çalışan, runtime-bağımsız yöntem.
ASSISTANT_PREFILL: str | None = None

@lru_cache(maxsize=1)
def _prompt_template() -> str:
    text = resources.read_text("prompts", "rerank_prompt.txt")
    if text is None:
        raise FileNotFoundError(
            "rerank_prompt.txt paket içinde bulunamadı (turkify/prompts/)"
        )
    return text


def _endpoint(path: str) -> str:
    """``base_url`` ile uç yolunu birleştirir (tek/çift eğik çizgiye dayanıklı)."""
    return f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    return headers


def available(*, timeout: float = 2.0) -> bool:
    """OpenAI-uyumlu sunucu erişilebilir mi? (GET ``/models``)"""
    try:
        request = urllib.request.Request(_endpoint("models"), headers=_headers())
        with urllib.request.urlopen(request, timeout=timeout) as resp:
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
    """HTTP hata gövdesinden sunucunun 'error' mesajını çıkarır."""
    try:
        body = exc.read().decode("utf-8")
        parsed = json.loads(body)
        # OpenAI biçimi {"error": {"message": ...}}; Ollama {"error": "..."}.
        error = parsed.get("error", body)
        if isinstance(error, dict):
            return error.get("message", json.dumps(error))
        return error
    except Exception:
        return str(exc)


# Bazı "düşünen" modeller reasoning'i yanıt metnine <think>...</think> olarak
# gömer; bunları ve şablon özel tokenlarını ayıklarız. (Bazı sunucular reasoning'i
# ayrı bir "reasoning_content" alanına koyar; onu zaten okumuyoruz.)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_OPEN_THINK_RE = re.compile(r"<think>.*", re.DOTALL | re.IGNORECASE)
_SPECIAL_TOKEN_RE = re.compile(r"<\|[^|]*\|>")


def _strip_thinking(text: str) -> str:
    """Yanıttan <think>...</think> bloğunu ve özel şablon tokenlarını temizler."""
    text = _THINK_RE.sub("", text)
    text = _OPEN_THINK_RE.sub("", text)  # kapanmamış (kesik) blok
    text = _SPECIAL_TOKEN_RE.sub("", text)
    return text.strip()


def _extract_content(data: dict) -> str | None:
    """OpenAI-uyumlu yanıttan asistan mesajının metnini çıkarır."""
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


def _chat_completion(prompt: str, model: str, timeout: float) -> str | None:
    """Tek bir ``/chat/completions`` isteği. Yanıt metnini döner, hata olursa ``None``."""
    # Belirleyicilik için temperature=0. max_tokens'i bilerek GÖNDERMİYORUZ:
    # "düşünen" modeller cevaptan önce uzun bir reasoning üretir; düşük bir tavan
    # cevabı (content) hiç oluşmadan keser. Üretim süresi zaten DEFAULT_TIMEOUT
    # ile sınırlıdır (asıl güvenlik ağı). İsteyen llm_options'a "max_tokens"
    # ekleyebilir. temperature de LLM_OPTIONS ile ezilebilir; model/messages/
    # stream sonradan zorla ayarlanır (doğruluğa etkili, kullanıcı bozmasın).
    payload = {"temperature": 0}
    payload.update(LLM_OPTIONS)
    payload["model"] = model
    messages = [{"role": "user", "content": prompt}]
    # Opsiyonel asistan prefill'i (ör. düşünmeyi atlatmak için boş <think> bloğu).
    # Son mesaj olarak eklenir; sunucu bunu sürdürür (continuation).
    if ASSISTANT_PREFILL:
        messages.append({"role": "assistant", "content": ASSISTANT_PREFILL})
    payload["messages"] = messages
    payload["stream"] = False
    endpoint = _endpoint("chat/completions")
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(),
    )
    _log.info("[Tier3] LLM istegi gonderiliyor: model=%r -> %s", model, endpoint)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = _http_detail(exc)
        if exc.code == 404:
            _log.warning(
                "[Tier3] Model %r bulunamadi (sunucuda yuklu mu?): %s", model, detail
            )
        elif exc.code in (401, 403):
            _log.warning(
                "[Tier3] Yetkilendirme hatasi (TURKIFY_API_KEY / api_key gerekebilir): %s",
                detail,
            )
        else:
            _log.warning("[Tier3] HTTP %s hatasi: %s", exc.code, detail)
        return None
    except TimeoutError:
        # TimeoutError, OSError'in alt sinifidir; aşağıdaki bloktan ÖNCE yakalanmalı.
        _log.warning(
            "[Tier3] LLM istegi zaman asimina ugradi (%.0f sn). Model yukleniyor "
            "olabilir; tekrar deneyin veya TURKIFY_TIMEOUT'u artirin.",
            timeout,
        )
        return None
    except (urllib.error.URLError, OSError) as exc:
        _log.warning(
            "[Tier3] LLM sunucusuna erisilemedi (calisiyor mu? base_url dogru mu?): %s",
            exc,
        )
        return None
    except json.JSONDecodeError:
        _log.warning("[Tier3] Sunucu yaniti cozulemedi (gecersiz JSON)")
        return None

    elapsed_ms = (time.perf_counter() - start) * 1000
    if data.get("error"):
        _log.warning("[Tier3] Sunucu hatasi: %s", data["error"])
        return None
    content = _extract_content(data)
    if content is None:
        _log.warning("[Tier3] Yanitta icerik yok (beklenmeyen yanit bicimi)")
        return None
    stripped = _strip_thinking(content)
    # Modelin (think bloklari ayiklanmis) ham yanitini logla; uzunsa kisaltilir.
    preview = stripped if len(stripped) <= 300 else stripped[:300] + "…"
    _log.info("[Tier3] LLM yaniti alindi (%.0f ms): %r", elapsed_ms, preview)
    return stripped


@lru_cache(maxsize=512)
def choose_batch(
    sentence: str,
    asks: tuple[tuple[str, tuple[str, ...]], ...],
    *,
    model: str | None = None,
    timeout: float | None = None,
) -> tuple[str | None, ...]:
    """Bir cümledeki tüm belirsiz kelimeleri TEK LLM isteğinde seçtirir.

    Kelime başına ayrı çağrı yerine, tüm cümle ve belirsiz kelimelerin adayları
    bir kez gönderilir; LLM her biri için seçim yapar. Bu, çok belirsizli
    cümlelerde gecikmeyi düşürür (N çağrı yerine 1).

    Args:
        sentence: Üzerinde çalışılan (Tier 1/2 uygulanmış) cümle.
        asks: ``(kelime, adaylar)`` ikilileri (hashlenebilir olması için tuple).
        model: OpenAI-uyumlu model adı.
        timeout: İstek zaman aşımı (sn).

    Returns:
        ``asks`` ile aynı sırada seçimler; bir soru çözülemezse o öğe ``None``.
    """
    if not asks:
        return ()
    # timeout/model çağrı anında çözülür; böylece config ile güncellenen
    # modül varsayılanları (DEFAULT_TIMEOUT) etki eder.
    effective_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
    response = _chat_completion(
        _build_batch_prompt(sentence, asks), model or DEFAULT_MODEL, effective_timeout
    )
    if response is None:
        return tuple(None for _ in asks)
    return _parse_batch(response, asks)
