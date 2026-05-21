"""Faz 7 — Öğrenen sistem (lokal kullanıcı tercih deposu).

DURUM: Faz 7 ŞİMDİLİK DEVRE DIŞIDIR. Bu modül çalışır durumda korunmuştur,
ancak ne ``engine`` (bkz. ``_FAZ7_ENABLED``) ne de CLI (``learn``/``forget``)
şu an buraya bağlıdır. Daha sonra ele alınacaktır.

Kullanıcı bir düzeltmeyi değiştirdiğinde (ör. ``ask`` → ``aşk``) tercih lokal
olarak saklanır ve sonraki düzeltmelerde uygulanır. Tüm veri lokal kalır;
hiçbir şey dışarı gönderilmez.

Depo basit bir JSON dosyasıdır: ``{ ascii_kelime_kucuk: tercih_kucuk }``.
Anahtar ve değer Türkçe küçük harfe normalize edilir; uygulama sırasında
kelimenin büyük/küçük harf deseni korunur (bkz. ``engine``).
"""

import json
import threading
from pathlib import Path

from turkify.protect import tr_lower

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "cache" / "preferences.json"

_lock = threading.Lock()
_storage_path = _DEFAULT_PATH
_cache: dict[str, str] | None = None


def set_storage_path(path: Path | str) -> None:
    """Depo dosyası yolunu değiştirir (öncelikle test izolasyonu için)."""
    global _storage_path, _cache
    _storage_path = Path(path)
    _cache = None


def _load() -> dict[str, str]:
    global _cache
    if _cache is None:
        if _storage_path.exists():
            try:
                _cache = json.loads(_storage_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                _cache = {}
        else:
            _cache = {}
    return _cache


def get_preference(ascii_word: str) -> str | None:
    """Kelime için kayıtlı kullanıcı tercihini (küçük harf) döner; yoksa ``None``."""
    if not ascii_word:
        return None
    return _load().get(tr_lower(ascii_word))


def record_preference(ascii_word: str, chosen: str) -> None:
    """Kullanıcının bir kelime için seçtiği doğru biçimi kalıcı olarak kaydeder.

    Args:
        ascii_word: Düzeltilen özgün (ASCII) kelime.
        chosen: Kullanıcının tercih ettiği doğru biçim.
    """
    if not ascii_word or not chosen:
        return
    with _lock:
        data = _load()
        data[tr_lower(ascii_word)] = tr_lower(chosen)
        _storage_path.parent.mkdir(parents=True, exist_ok=True)
        _storage_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def forget(ascii_word: str) -> bool:
    """Bir kelimeye ait tercihi siler. Silindiyse ``True`` döner."""
    with _lock:
        data = _load()
        key = tr_lower(ascii_word)
        if key not in data:
            return False
        del data[key]
        self_path = _storage_path
        self_path.parent.mkdir(parents=True, exist_ok=True)
        self_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return True
