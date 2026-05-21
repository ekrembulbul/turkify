"""Orkestrasyon — düzeltme pipeline'ının giriş noktası.

Akış (kademeli/hibrit):
    metin → koruma aralıkları → Tier 1 deasciify → korunan aralıkları geri yaz
          → (opsiyonel) Tier 2 morfolojik doğrulama/düzeltme

Tier 2 yalnızca ``zeyrek`` kuruluysa ve ``use_morphology=True`` iken çalışır;
aksi hâlde sistem Faz 1 deterministik davranışını korur. ``use_llm`` Tier 3
(LLM) için kontrattadır ve Faz 1-2'de etkisizdir.
"""

from functools import lru_cache

from turkify import morphology
from turkify.candidates import generate_candidates
from turkify.deasciifier import deasciify
from turkify.protect import load_protected_words, protected_spans
from turkify.reconstruct import restore_spans
from turkify.tokenizer import tokenize


@lru_cache(maxsize=1)
def _protected_words() -> frozenset[str]:
    """Korumalı kelime listesini yükler ve süreç boyunca önbellekler."""
    return load_protected_words()


def _overlaps_protected(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    """[start, end) aralığı korunan aralıklardan biriyle kesişiyor mu?"""
    return any(p_start < end and start < p_end for p_start, p_end in spans)


def _correct_word_tier2(ascii_word: str, tier1_word: str) -> str:
    """Bir kelimeyi morfolojik doğrulamayla gözden geçirir.

    Tier 1'in ürettiği kelime geçerliyse aynen bırakılır. Geçersizse, orijinal
    ASCII kelimenin diakritik adayları arasında **tam olarak bir** geçerli aday
    varsa ona geçilir. Sıfır ya da birden fazla geçerli aday varsa Tier 1
    kararı korunur (birden fazla aday bağlam gerektirir → ileride Tier 3).
    """
    if morphology.is_valid_word(tier1_word):
        return tier1_word

    valid = [c for c in generate_candidates(ascii_word) if morphology.is_valid_word(c)]
    if len(valid) == 1:
        return valid[0]
    return tier1_word


def _apply_tier2(
    original: str, corrected: str, spans: list[tuple[int, int]]
) -> str:
    """Korunmayan kelimelere Tier 2 morfolojik düzeltmeyi uygular.

    ``original`` ve ``corrected`` aynı uzunlukta olmalıdır (Tier 1 ve aday
    üretimi tek karakterlik yerine-koyma yapar, uzunluğu değiştirmez).
    """
    result = list(corrected)
    for token in tokenize(corrected):
        if not token.is_word:
            continue
        if _overlaps_protected(token.start, token.end, spans):
            continue
        ascii_word = original[token.start : token.end]
        new_word = _correct_word_tier2(ascii_word, token.text)
        if new_word != token.text:
            result[token.start : token.end] = new_word
    return "".join(result)


def correct(
    text: str, *, use_llm: bool = False, use_morphology: bool = True
) -> str:
    """ASCII Türkçe metni doğru diakritiklerle düzeltir.

    Boşluk, noktalama ve büyük/küçük harf yapısı korunur. Korumalı kelimeler,
    URL/e-posta/sayı/kod parçaları ve zaten Türkçe karakter içeren kelimeler
    dönüştürülmeden bırakılır.

    Args:
        text: ASCII (şapkasız) Türkçe metin.
        use_llm: İleriki Tier 3 (LLM) için ayrılmıştır. Faz 1-2'de etkisizdir.
        use_morphology: Tier 2 morfolojik doğrulamayı etkinleştirir. ``zeyrek``
            kurulu değilse otomatik olarak atlanır (sistem deterministik kalır).

    Returns:
        Diakritikleri restore edilmiş metin.
    """
    if not text:
        return text

    spans = protected_spans(text, _protected_words())
    corrected = deasciify(text)
    corrected = restore_spans(corrected, text, spans)

    if use_morphology and morphology.available():
        corrected = _apply_tier2(text, corrected, spans)

    return corrected
