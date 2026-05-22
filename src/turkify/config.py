"""Çok-platform yapılandırma yükleyici.

Tüm çalışma zamanı ayarları bir JSON config dosyasında toplanır. JSON seçildi
çünkü hem Python (stdlib ``json``) hem de ileride başka araçlar tarafından
bağımlılıksız okunabilir.

Konum (``TURKIFY_CONFIG`` ile override edilebilir):
  * macOS / Linux : ``$XDG_CONFIG_HOME/turkify/config.json`` veya
                    ``~/.config/turkify/config.json``
  * Windows       : ``%APPDATA%\\turkify\\config.json``

Öncelik (yüksekten düşüğe): CLI bayrağı > ortam değişkeni > config > varsayılan.
Bu modül yalnızca "config + varsayılan" katmanını verir; env/bayrak override'ı
çağıran taraf (CLI/agent) uygular.
"""

import json
import os
from pathlib import Path

# Yerleşik varsayılanlar. ``model`` bilinçli olarak None: model config'te
# belirtilmezse Tier 3 (LLM) çalışmaz (otomatik model tespiti yapılmaz).
DEFAULTS: dict = {
    "model": None,
    "use_llm": False,
    "use_morphology": True,
    "timeout": 60.0,
    "ollama_host": "http://localhost:11434",
    "hotkey": {"mods": ["ctrl", "alt", "cmd"], "key": "t"},
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
    except (json.JSONDecodeError, OSError):
        return settings
    if isinstance(data, dict):
        settings.update({key: data[key] for key in data if key in DEFAULTS})
    return settings


def apply(settings: dict) -> None:
    """Config'teki Tier 3 ayarlarını (timeout, ollama_host) reranker'a uygular.

    Model açıkça ``correct(model=...)`` ile geçirilir; burada yalnızca modül
    düzeyindeki diğer çalışma zamanı varsayılanları güncellenir.
    """
    from turkify import reranker

    if settings.get("timeout") is not None:
        reranker.DEFAULT_TIMEOUT = float(settings["timeout"])
    if settings.get("ollama_host"):
        reranker.OLLAMA_HOST = settings["ollama_host"]

