"""Çok-platform yapılandırma yükleyici.

Tüm çalışma zamanı ayarları bir JSON config dosyasında toplanır. JSON seçildi
çünkü hem Python (stdlib ``json``) hem de ileride başka araçlar tarafından
bağımlılıksız okunabilir.

Konum (``TURKIFY_CONFIG`` ile override edilebilir):
  * macOS / Linux : ``$XDG_CONFIG_HOME/turkify/config.json`` veya
                    ``~/.config/turkify/config.json``
  * Windows       : ``%APPDATA%\\turkify\\config.json``

Öncelik (yüksekten düşüğe): CLI bayrağı > ortam değişkeni > config > varsayılan.
``load()`` yalnızca "config + varsayılan" katmanını verir; ``resolve()`` bunun
üstüne ``TURKIFY_*`` env ve CLI override katmanlarını ekleyerek tam önceliği
uygular. ``apply()`` çözülmüş ayarları reranker modülüne yazar.
"""

import json
import logging
import os
from pathlib import Path

# Config sorunları "turkify" günlüğüne WARNING olarak yazılır; --verbose olmasa
# bile (Python'un last-resort handler'ı sayesinde) stderr'de görünür.
_log = logging.getLogger("turkify")

# Yerleşik varsayılanlar. ``model`` bilinçli olarak None: model config'te
# belirtilmezse Tier 3 (LLM) çalışmaz (otomatik model tespiti yapılmaz).
DEFAULTS: dict = {
    "model": None,
    "use_llm": False,
    "use_morphology": True,
    "timeout": 60.0,
    # OpenAI-uyumlu LLM sunucusunun kök adresi (sona /chat/completions eklenir).
    # Varsayılan Ollama'nın yerel OpenAI-uyumlu ucu; LM Studio için ör.
    # "http://localhost:1234/v1".
    "base_url": "http://localhost:11434/v1",
    # Yerel sunucular genelde anahtar istemez; gerekiyorsa buraya yazılır.
    "api_key": None,
    # /chat/completions isteğine eklenecek sunucu/model-özel seçenekler. Ör.
    # düşünmeyi kapatmak: {"chat_template_kwargs": {"enable_thinking": false}}.
    "llm_options": {},
    # İstek sonuna eklenecek asistan prefill'i. "düşünen" modellerde reasoning'i
    # atlatmak için "<think>\n\n</think>\n\n" verilebilir (bkz. reranker).
    "assistant_prefill": None,
    "hotkey": {"mods": ["ctrl", "alt", "cmd"], "key": "a"},
}


def config_path() -> Path:
    """Platforma uygun config dosyası yolunu döner (``TURKIFY_CONFIG`` öncelikli)."""
    override = os.environ.get("TURKIFY_CONFIG")
    if override:
        return Path(override)
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:  # macOS / Linux (XDG)
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "turkify" / "config.json"


def load(path: Path | str | None = None) -> dict:
    """Config dosyasını yükler ve varsayılanlarla birleştirir.

    Dosya yoksa veya bozuksa yalnızca varsayılanlar döner (config opsiyoneldir).

    Args:
        path: Config yolu; ``None`` ise ``config_path()`` kullanılır.

    Returns:
        Birleştirilmiş ayar sözlüğü (varsayılanlar + config).
    """
    settings = dict(DEFAULTS)
    file_path = Path(path) if path is not None else config_path()
    if not file_path.exists():
        return settings
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # Sık tuzak: dosyaya // yorum eklemek (JSON yorum desteklemez). Sessizce
        # varsayılana düşmek yerine uyar; aksi hâlde config görünüşte "duruyor"
        # ama hiç uygulanmıyormuş gibi şaşırtıcı davranış olur.
        _log.warning(
            "[config] %s gecersiz JSON (yorum/virgul hatasi olabilir; JSON yorum "
            "desteklemez) -> varsayilanlar kullaniliyor: %s",
            file_path, exc,
        )
        return settings
    except OSError as exc:
        _log.warning("[config] %s okunamadi -> varsayilanlar kullaniliyor: %s", file_path, exc)
        return settings
    if isinstance(data, dict):
        settings.update({key: data[key] for key in data if key in DEFAULTS})
    return settings


_TRUE_STRINGS = {"1", "true", "yes", "on", "evet"}
_FALSE_STRINGS = {"0", "false", "no", "off", "hayir"}


def _to_bool(raw: str) -> bool:
    low = raw.strip().lower()
    if low in _TRUE_STRINGS:
        return True
    if low in _FALSE_STRINGS:
        return False
    raise ValueError(f"bool degeri bekleniyordu, {raw!r} alindi")


# config anahtarı -> (TURKIFY_* ortam değişkeni, dönüştürücü). Env katmanı
# config dosyasını ezer, CLI bayrağı da env'i ezer (bkz. resolve()).
_ENV_MAP: dict = {
    "model": ("TURKIFY_MODEL", str),
    "use_llm": ("TURKIFY_USE_LLM", _to_bool),
    "use_morphology": ("TURKIFY_USE_MORPHOLOGY", _to_bool),
    "timeout": ("TURKIFY_TIMEOUT", float),
    "base_url": ("TURKIFY_BASE_URL", str),
    "api_key": ("TURKIFY_API_KEY", str),
    "llm_options": ("TURKIFY_LLM_OPTIONS", json.loads),
    "assistant_prefill": ("TURKIFY_ASSISTANT_PREFILL", str),
}


def resolve(overrides: dict | None = None, path: Path | str | None = None) -> dict:
    """Ayarları tam öncelik sırasıyla çözer.

    Öncelik (yüksekten düşüğe): CLI override > ``TURKIFY_*`` env > config dosyası
    > yerleşik varsayılan. ``overrides`` içinde değeri ``None`` olan anahtarlar
    "verilmedi" sayılır (alt katman korunur).

    Args:
        overrides: CLI bayraklarından gelen değerler (``None`` = verilmedi).
        path: Config yolu; ``None`` ise ``config_path()``.

    Returns:
        Çözülmüş ayar sözlüğü.
    """
    settings = load(path)
    for key, (env_name, convert) in _ENV_MAP.items():
        raw = os.environ.get(env_name)
        if not raw:  # ayarlanmamış veya boş → atla
            continue
        try:
            settings[key] = convert(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            _log.warning("[config] %s degeri gecersiz (%r), yok sayiliyor: %s", env_name, raw, exc)
    if overrides:
        settings.update({key: value for key, value in overrides.items() if value is not None})
    return settings


def apply(settings: dict) -> None:
    """Config'teki Tier 3 ayarlarını (timeout, base_url, api_key, llm_options) reranker'a uygular.

    Model açıkça ``correct(model=...)`` ile geçirilir; burada yalnızca modül
    düzeyindeki diğer çalışma zamanı varsayılanları güncellenir.
    """
    from turkify import reranker

    if settings.get("timeout") is not None:
        reranker.DEFAULT_TIMEOUT = float(settings["timeout"])
    if settings.get("base_url"):
        reranker.BASE_URL = settings["base_url"]
    if settings.get("api_key"):
        reranker.API_KEY = settings["api_key"]
    if settings.get("llm_options"):
        reranker.LLM_OPTIONS = settings["llm_options"]
    if settings.get("assistant_prefill"):
        reranker.ASSISTANT_PREFILL = settings["assistant_prefill"]

