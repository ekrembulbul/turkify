"""Orkestrasyon — düzeltme pipeline'ının giriş noktası.

Kademeli/hibrit akış:
    metin → koruma aralıkları → Tier 1 deasciify → korunan aralıkları geri yaz
          → kelime bazında çözümleme:
                kullanıcı tercihi (Faz 7) > Tier 2 morfoloji > Tier 3 LLM > Tier 1

Her katman opsiyoneldir ve graceful biçimde atlanır:
  * Tier 2 yalnızca ``zeyrek`` kuruluysa ve ``use_morphology=True`` iken,
  * Tier 3 yalnızca ``use_llm=True`` ve Ollama erişilebilirken çalışır.
Hiçbiri yoksa sistem Faz 1 deterministik davranışını korur.
"""

from functools import lru_cache

from turkify import learn, morphology, reranker
from turkify.candidates import generate_candidates
from turkify.deasciifier import deasciify
from turkify.protect import load_protected_words, protected_spans, tr_lower
from turkify.reconstruct import restore_spans
from turkify.tokenizer import tokenize


@lru_cache(maxsize=1)
def _protected_words() -> frozenset[str]:
    """Korumalı kelime listesini yükler ve süreç boyunca önbellekler."""
    return load_protected_words()


def _overlaps_protected(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    """[start, end) aralığı korunan aralıklardan biriyle kesişiyor mu?"""
    return any(p_start < end and start < p_end for p_start, p_end in spans)


def _apply_preference(candidates: list[str], preference: str) -> str | None:
    """Kullanıcı tercihine (küçük harf) uyan adayı, kelimenin case'ini koruyarak döner."""
    for candidate in candidates:
        if tr_lower(candidate) == preference:
            return candidate
    return None


def _resolve_word(
    ascii_word: str,
    tier1_word: str,
    sentence: str,
    *,
    use_morphology: bool,
    use_llm: bool,
) -> str:
    """Bir kelimeyi katmanlı önceliklerle çözer.

    Öncelik: kullanıcı tercihi → tek geçerli aday → (çoklu geçerli + LLM) → Tier 1.
    """
    preference = learn.get_preference(ascii_word)
    if preference is None and not use_morphology:
        return tier1_word  # hızlı yol: yapılacak bir şey yok

    candidates = generate_candidates(ascii_word)
    if not candidates:  # çok fazla çevrilebilir karakter → atla
        return tier1_word

    if preference is not None:
        chosen = _apply_preference(candidates, preference)
        if chosen is not None:
            return chosen

    if not (use_morphology and morphology.available()):
        return tier1_word

    valid = [c for c in candidates if morphology.is_valid_word(c)]
    if not valid:
        return tier1_word

    # Hassasiyet önceliği: Tier 1 geçerli bir kelime ürettiyse ona güveniriz.
    # Deterministik çekirdek yüksek isabetlidir; geçerli bir seçimi yalnızca
    # başka geçerli aday var diye ezmek (ör. "sana"→"şana") false positive
    # üretir. Geçerli-ama-bağlamsal-yanlış override'ı frekans modeline (Faz 5)
    # bırakılır.
    if tier1_word in valid:
        return tier1_word

    # Buradan itibaren Tier 1 geçersiz bir kelime üretmiştir.
    if len(valid) == 1:
        return valid[0]  # tek geçerli alternatif → düzelt (Tier 2)

    # Birden fazla geçerli alternatif ve Tier 1 başarısız → bağlam gerekir (Tier 3).
    if use_llm:
        choice = reranker.choose(sentence, ascii_word, tuple(valid))
        if choice is not None:
            return choice
    return tier1_word


def _resolve_words(
    original: str,
    corrected: str,
    spans: list[tuple[int, int]],
    *,
    use_morphology: bool,
    use_llm: bool,
) -> str:
    """Korunmayan kelimelere katmanlı çözümlemeyi uygular.

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
        new_word = _resolve_word(
            ascii_word,
            token.text,
            corrected,
            use_morphology=use_morphology,
            use_llm=use_llm,
        )
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
        use_llm: Tier 3 LLM rerank'i (Ollama) etkinleştirir. Yalnızca birden
            fazla geçerli aday bağlam gerektirdiğinde ve Ollama erişilebilirken
            kullanılır; aksi hâlde deterministik karar korunur.
        use_morphology: Tier 2 morfolojik doğrulamayı etkinleştirir. ``zeyrek``
            kurulu değilse otomatik atlanır.

    Returns:
        Diakritikleri restore edilmiş metin.
    """
    if not text:
        return text

    spans = protected_spans(text, _protected_words())
    corrected = deasciify(text)
    corrected = restore_spans(corrected, text, spans)

    return _resolve_words(
        text, corrected, spans, use_morphology=use_morphology, use_llm=use_llm
    )
