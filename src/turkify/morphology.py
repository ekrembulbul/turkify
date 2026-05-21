"""Tier 2 — morfolojik doğrulama (opsiyonel ``zeyrek`` sarmalayıcısı).

Bir kelimenin morfolojik olarak geçerli bir Türkçe kelime olup olmadığını
söyler. Türkçe sondan eklemeli olduğundan, çekimli biçimleri (ör.
``kitaplarımızdan``) de doğrular — bu, sabit bir frekans sözlüğünün yapamadığı
şeydir.

``zeyrek`` kurulu değilse katman sessizce devre dışı kalır (``available()``
``False`` döner) ve sistem Faz 1 deterministik davranışını korur. ``zeyrek``
dahili olarak NLTK tokenizer'ına başvurur; bunu baypas etmek için kendi
``analyzer`` çekirdeğini tek kelime üzerinde kullanırız.
"""

import logging
from functools import lru_cache

from turkify.protect import tr_lower

try:
    import zeyrek as _zeyrek
except ImportError:  # pragma: no cover - ortama bağlı
    _zeyrek = None


def available() -> bool:
    """Morfolojik doğrulama kullanılabilir mi (zeyrek kurulu mu)?"""
    return _zeyrek is not None


@lru_cache(maxsize=1)
def _analyzer():
    """zeyrek çekirdek analizörünü yükler (tek seferlik, ~1 sn) ve önbellekler."""
    # zeyrek analiz sonuçlarını INFO seviyesinde stdout/stderr'e loglar;
    # bu, CLI çıktımızı kirletmemesi için susturulur.
    logging.getLogger("zeyrek").setLevel(logging.CRITICAL)
    return _zeyrek.MorphAnalyzer().analyzer


@lru_cache(maxsize=4096)
def is_valid_word(word: str) -> bool:
    """Kelime morfolojik olarak geçerli bir Türkçe kelime mi?

    Karşılaştırma Türkçe küçük harfe normalize edilerek yapılır; böylece
    cümle başı büyük harfli kelimeler de doğru değerlendirilir. ``zeyrek``
    yoksa daima ``False`` döner (katman devre dışı).

    Args:
        word: Doğrulanacak kelime.

    Returns:
        Geçerliyse ``True``, değilse veya katman devre dışıysa ``False``.
    """
    if _zeyrek is None or not word:
        return False
    try:
        return bool(list(_analyzer().analyze(tr_lower(word))))
    except Exception:
        # Analizör beklenmedik girdide hata verirse kelimeyi "doğrulanamadı"
        # sayarız; çağıran taraf güvenli tarafta (Tier 1) kalır.
        return False
