"""Orkestrasyon — düzeltme pipeline'ının giriş noktası.

Kademeli/hibrit akış:
    metin → koruma aralıkları → Tier 1 deasciify → korunan aralıkları geri yaz
          → kelime bazında çözümleme:
                Tier 2 (morfoloji + frekans) > Tier 3 LLM > Tier 1

Her katman opsiyoneldir ve graceful biçimde atlanır:
  * Tier 2 yalnızca ``zeyrek`` kuruluysa ve ``use_morphology=True`` iken,
  * Tier 3 yalnızca ``use_llm=True`` ve Ollama erişilebilirken çalışır.
Hiçbiri yoksa sistem Faz 1 deterministik davranışını korur.

NOT: Faz 7 (öğrenen sistem / kullanıcı tercihi) şimdilik DEVRE DIŞIDIR
(``_FAZ7_ENABLED = False``). İlgili kod yerinde tutuldu; tek satırla yeniden
etkinleştirilebilir. Etkinken tercih, tüm katmanların önüne geçer.
"""

import logging
from functools import lru_cache

from turkify import frequency, learn, morphology, reranker
from turkify.candidates import generate_candidates
from turkify.deasciifier import deasciify
from turkify.protect import load_protected_words, protected_spans, tr_lower
from turkify.reconstruct import restore_spans
from turkify.tokenizer import tokenize

# Karar günlüğü. Varsayılan olarak sessizdir; CLI'deki --verbose bunu
# stderr'e açar (bkz. __main__._enable_verbose).
_log = logging.getLogger("turkify")

# Faz 7 (öğrenen sistem) ana anahtarı. Şimdilik kapalı; daha sonra ele alınacak.
_FAZ7_ENABLED = False

# Bir adayın "baskın" sayılması için ikinci adaydan kaç kat daha sık olması
# gerektiği. Baskınsa frekansla deterministik seçilir; değilse belirsizdir.
_FREQ_DOMINANCE_FACTOR = 5


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


def _dominant_by_frequency(valid: list[str]) -> str | None:
    """Adaylar arasında frekansça baskın olanı döner; yoksa ``None``.

    En sık adayın frekansı, ikinci adayınkinin ``_FREQ_DOMINANCE_FACTOR`` katı
    veya üzeriyse "baskın" sayılıp deterministik seçilir. Aksi hâlde (frekanslar
    yakın veya tümü bilinmiyor) belirsizdir → ``None``.
    """
    ranked = sorted(valid, key=frequency.get_frequency, reverse=True)
    top_freq = frequency.get_frequency(ranked[0])
    if top_freq <= 0:
        return None
    second_freq = frequency.get_frequency(ranked[1]) if len(ranked) > 1 else 0
    if top_freq >= _FREQ_DOMINANCE_FACTOR * max(second_freq, 1):
        return ranked[0]
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

    Öncelik: (Faz 7 — devre dışı) → tek geçerli aday → baskın frekans → LLM → Tier 1.
    """
    if not (use_morphology and morphology.available()):
        return tier1_word

    candidates = generate_candidates(ascii_word)
    if not candidates:  # çok fazla çevrilebilir karakter → atla
        return tier1_word

    # Faz 7 (kullanıcı tercihi) şimdilik devre dışı. _FAZ7_ENABLED=True
    # yapıldığında tercih, aşağıdaki morfoloji katmanının önüne geçer.
    # (Yeniden etkinleştirirken: tercih morfoloji kurulu olmasa da uygulanmak
    # isteniyorsa bu blok yukarıdaki gate'in önüne taşınmalıdır.)
    if _FAZ7_ENABLED:
        preference = learn.get_preference(ascii_word)
        if preference is not None:
            chosen = _apply_preference(candidates, preference)
            if chosen is not None:
                return chosen

    valid = [c for c in candidates if morphology.is_valid_word(c)]
    if not valid:
        return tier1_word

    if len(valid) == 1:
        if valid[0] != tier1_word:
            _log.info(
                "[Tier2] %r: Tier1 %r gecersiz -> %r (tek gecerli aday)",
                ascii_word, tier1_word, valid[0],
            )
        return valid[0]

    # Birden fazla geçerli aday → önce frekansla ayır. Baskın bir aday varsa
    # (ör. "sana"≫"şana", "çiş"≫"çis") deterministik seçilir; bu hem Tier 1'in
    # bağlamsal hatasını düzeltir hem de yaygın kelimelerde LLM'e gerek bırakmaz.
    dominant = _dominant_by_frequency(valid)
    if dominant is not None:
        if dominant != tier1_word:
            _log.info(
                "[Tier2-frekans] %r: %r -> %r (baskin frekans)",
                ascii_word, tier1_word, dominant,
            )
        return dominant

    # Frekanslar yakın veya bilinmiyor → gerçek bağlamsal belirsizlik (Tier 3).
    if use_llm:
        _log.info(
            "[Tier3] %r: belirsiz adaylar %s; LLM'e soruluyor", ascii_word, valid
        )
        choice = reranker.choose(sentence, ascii_word, tuple(valid))
        if choice is not None:
            _log.info("[Tier3] %r: LLM secti -> %r", ascii_word, choice)
            return choice
        _log.info(
            "[Tier3] %r: LLM yanit vermedi; Tier1 %r korunuyor",
            ascii_word, tier1_word,
        )
    else:
        _log.info(
            "[Tier3] %r: belirsiz adaylar %s, --llm kapali; Tier1 %r korunuyor",
            ascii_word, valid, tier1_word,
        )
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
