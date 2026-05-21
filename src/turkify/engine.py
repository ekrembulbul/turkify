"""Orkestrasyon — düzeltme pipeline'ının giriş noktası.

Akış (Faz 1, deterministik):
    metin → koruma aralıkları → Tier 1 deasciify → korunan aralıkları geri yaz

``use_llm`` parametresi ileriki fazlar (Tier 3) için kontrattadır; Faz 1'de
yoktur ve ``True`` verilse bile davranış değişmez (sistem tam offline kalır).
"""

from functools import lru_cache

from turkify.deasciifier import deasciify
from turkify.protect import load_protected_words, protected_spans
from turkify.reconstruct import restore_spans


@lru_cache(maxsize=1)
def _protected_words() -> frozenset[str]:
    """Korumalı kelime listesini yükler ve süreç boyunca önbellekler."""
    return load_protected_words()


def correct(text: str, *, use_llm: bool = False) -> str:
    """ASCII Türkçe metni doğru diakritiklerle düzeltir.

    Boşluk, noktalama ve büyük/küçük harf yapısı korunur. Korumalı kelimeler,
    URL/e-posta/sayı/kod parçaları ve zaten Türkçe karakter içeren kelimeler
    dönüştürülmeden bırakılır.

    Args:
        text: ASCII (şapkasız) Türkçe metin.
        use_llm: İleriki Tier 3 (LLM) için ayrılmıştır. Faz 1'de etkisizdir;
            sistem her durumda deterministik ve offline çalışır.

    Returns:
        Diakritikleri restore edilmiş metin.
    """
    if not text:
        return text

    spans = protected_spans(text, _protected_words())
    corrected = deasciify(text)
    return restore_spans(corrected, text, spans)
