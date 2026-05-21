"""Türkçe kelime-frekans sözlüğü (aday sıralama / escalation kararı için).

Birden fazla morfolojik olarak geçerli aday olduğunda, hangisinin gerçekte daha
sık kullanıldığını bilmek belirsizliği çözer:
  * Bir aday baskın biçimde daha sıksa → deterministik seçilir (LLM gerekmez).
  * Frekanslar yakınsa → gerçek bağlamsal belirsizliktir, Tier 3'e (LLM) yükseltilir.

Veri ``data/tr_frequency.txt`` dosyasından okunur (``kelime sayı`` biçimi).
Dosya yoksa katman graceful biçimde devre dışı kalır (tüm frekanslar 0 döner).
"""

from functools import lru_cache
from pathlib import Path

from turkify.protect import tr_lower

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "tr_frequency.txt"


@lru_cache(maxsize=1)
def _frequencies() -> dict[str, int]:
    """Frekans dosyasını okur ve ``{kelime: sayı}`` sözlüğü olarak önbellekler."""
    if not _DEFAULT_PATH.exists():
        return {}

    freqs: dict[str, int] = {}
    for line in _DEFAULT_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        word, count = parts
        try:
            freqs[tr_lower(word)] = int(count)
        except ValueError:
            continue
    return freqs


def available() -> bool:
    """Frekans sözlüğü yüklenebildi mi (veri dosyası var ve boş değil)?"""
    return bool(_frequencies())


def get_frequency(word: str) -> int:
    """Kelimenin korpus frekansını döner; bilinmiyorsa 0.

    Karşılaştırma Türkçe küçük harfe normalize edilir.
    """
    if not word:
        return 0
    return _frequencies().get(tr_lower(word), 0)
