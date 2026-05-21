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

import importlib.util
import logging
from functools import lru_cache

from turkify.protect import tr_lower


@lru_cache(maxsize=1)
def available() -> bool:
    """Morfolojik doğrulama kullanılabilir mi (zeyrek kurulu mu)?

    ``zeyrek`` modülünü içe aktarmadan yalnızca kurulu olup olmadığını kontrol
    eder; böylece ağır içe aktarma (zeyrek → nltk) yalnızca gerçekten analiz
    yapılacağı zaman gerçekleşir.
    """
    return importlib.util.find_spec("zeyrek") is not None


@lru_cache(maxsize=1)
def _analyzer():
    """zeyrek çekirdek analizörünü yükler (tek seferlik, ~1 sn) ve önbellekler."""
    import zeyrek  # tembel içe aktarma: ağır (nltk) ve yalnızca gerektiğinde

    # zeyrek analiz sonuçlarını INFO seviyesinde loglar; CLI çıktımızı
    # kirletmemesi için susturulur.
    logging.getLogger("zeyrek").setLevel(logging.CRITICAL)
    return zeyrek.MorphAnalyzer().analyzer


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
    if not word or not available():
        return False
    try:
        return bool(list(_analyzer().analyze(tr_lower(word))))
    except Exception:
        # Analizör beklenmedik girdide hata verirse kelimeyi "doğrulanamadı"
        # sayarız; çağıran taraf güvenli tarafta (Tier 1) kalır.
        return False
