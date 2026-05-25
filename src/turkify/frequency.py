"""Türkçe kelime-frekans sözlüğü (aday sıralama / escalation kararı için).

Birden fazla morfolojik olarak geçerli aday olduğunda, hangisinin gerçekte daha
sık kullanıldığını bilmek belirsizliği çözer:
  * Bir aday baskın biçimde daha sıksa → deterministik seçilir (LLM gerekmez).
  * Frekanslar yakınsa → gerçek bağlamsal belirsizliktir, Tier 3'e (LLM) yükseltilir.

Veri ``turkify/data/tr_frequency.txt`` (pakete gömülü) dosyasından okunur
(``kelime sayı`` biçimi). Dosya yoksa katman graceful biçimde devre dışı kalır
(tüm frekanslar 0 döner).
"""

from functools import lru_cache

from turkify import resources
from turkify.protect import tr_lower


@lru_cache(maxsize=1)
def _frequencies() -> dict[str, int]:
    """Frekans dosyasını okur ve ``{kelime: sayı}`` sözlüğü olarak önbellekler."""
    text = resources.read_text("data", "tr_frequency.txt")
    if text is None:
        return {}

    freqs: dict[str, int] = {}
    for line in text.splitlines():
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
