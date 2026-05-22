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
# gerektiği. Oran bunun altındaysa (ör. "tür"/"tur" = 6.3) aday yakın kabul
# edilir ve karar bağlama (LLM) bırakılır; çok üstündeyse (ör. "böyle"/"boyle"
# = 194) ezici baskındır ve deterministik seçilir. Mutlak sıklık eşiği yerine
# oran kullanılır; çünkü korpus ASCII-yazımları da içerdiğinden ("boyle"=1860)
# mutlak eşik gerçek baskınlığı da yanlışlıkla LLM'e iterdi.
_FREQ_DOMINANCE_FACTOR = 10


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


def _resolve_word_deterministic(
    ascii_word: str,
    tier1_word: str,
    *,
    use_morphology: bool,
) -> tuple[str, tuple[str, ...] | None]:
    """Bir kelimeyi LLM olmadan çözer.

    Döner: ``(sonuc, belirsiz_adaylar)``. ``belirsiz_adaylar`` yalnızca kelime
    Tier 3 (LLM) gerektiriyorsa (çoklu geçerli aday, frekans baskın değil)
    doludur; o durumda ``sonuc`` deterministik yedek (Tier 1) çıktısıdır.
    """
    if not (use_morphology and morphology.available()):
        return tier1_word, None

    candidates = generate_candidates(ascii_word)
    if not candidates:  # çok fazla çevrilebilir karakter → atla
        return tier1_word, None

    # Faz 7 (kullanıcı tercihi) şimdilik devre dışı (bkz. _FAZ7_ENABLED).
    if _FAZ7_ENABLED:
        preference = learn.get_preference(ascii_word)
        if preference is not None:
            chosen = _apply_preference(candidates, preference)
            if chosen is not None:
                return chosen, None

    valid = [c for c in candidates if morphology.is_valid_word(c)]
    if not valid:
        return tier1_word, None

    if len(valid) == 1:
        if valid[0] != tier1_word:
            _log.info(
                "[Tier2] %r: Tier1 %r gecersiz -> %r (tek gecerli aday)",
                ascii_word, tier1_word, valid[0],
            )
        return valid[0], None

    # Birden fazla geçerli aday → önce frekansla ayır. Baskın bir aday varsa
    # (ör. "sana"≫"şana", "çiş"≫"çis") deterministik seçilir.
    dominant = _dominant_by_frequency(valid)
    if dominant is not None:
        if dominant != tier1_word:
            _log.info(
                "[Tier2-frekans] %r: %r -> %r (baskin frekans)",
                ascii_word, tier1_word, dominant,
            )
        return dominant, None

    # Frekanslar yakın/bilinmiyor → gerçek bağlamsal belirsizlik → Tier 3'e bırak.
    return tier1_word, tuple(valid)


def _apply_tier3_batch(
    result: list[str],
    sentence: str,
    pending: list[tuple],
    *,
    use_llm: bool,
    model: str | None,
) -> None:
    """Belirsiz kelimeleri TEK LLM isteğinde çözer ve ``result``'a uygular.

    ``pending`` öğeleri ``(token, ascii_word, candidates)`` üçlüleridir. LLM
    kapalıysa ya da bir kelime için seçim gelmezse o kelime Tier 1 hâlinde kalır.
    """
    if not use_llm:
        for token, ascii_word, cands in pending:
            _log.info(
                "[Tier3] %r: belirsiz adaylar %s, --llm kapali; Tier1 %r korunuyor",
                ascii_word, list(cands), token.text,
            )
        return

    asks = tuple((ascii_word, cands) for _token, ascii_word, cands in pending)
    _log.info(
        "[Tier3] %d belirsiz kelime tek istekte LLM'e soruluyor: %s",
        len(asks), [word for word, _ in asks],
    )
    choices = reranker.choose_batch(
        sentence, asks, model=model or reranker.DEFAULT_MODEL
    )
    for (token, ascii_word, cands), choice in zip(pending, choices):
        if choice is not None and choice in cands:
            _log.info("[Tier3] %r: LLM secti -> %r", ascii_word, choice)
            result[token.start : token.end] = choice
        else:
            _log.info(
                "[Tier3] %r: LLM secmedi; Tier1 %r korunuyor", ascii_word, token.text
            )


def _resolve_words(
    original: str,
    corrected: str,
    spans: list[tuple[int, int]],
    *,
    use_morphology: bool,
    use_llm: bool,
    model: str | None = None,
) -> str:
    """Korunmayan kelimeleri çözer: önce deterministik, sonra belirsizleri tek
    batch LLM isteğiyle.

    ``original`` ve ``corrected`` aynı uzunlukta olmalıdır (Tier 1 ve aday
    üretimi tek karakterlik yerine-koyma yapar, uzunluğu değiştirmez).
    """
    result = list(corrected)
    pending: list[tuple] = []  # (token, ascii_word, candidates)
    for token in tokenize(corrected):
        if not token.is_word:
            continue
        if _overlaps_protected(token.start, token.end, spans):
            continue
        ascii_word = original[token.start : token.end]
        resolved, ambiguous = _resolve_word_deterministic(
            ascii_word, token.text, use_morphology=use_morphology
        )
        if ambiguous is None:
            if resolved != token.text:
                result[token.start : token.end] = resolved
        else:
            pending.append((token, ascii_word, ambiguous))

    if pending:
        # LLM'e verilecek bağlam: belirsiz OLMAYAN kelimeler düzeltilmiş hâlde
        # (result), belirsiz kelimeler ise orijinal ASCII hâlinde gösterilir.
        # Böylece Tier 1'in (bazen yanlış) tahmini LLM'i yanıltmaz; LLM her
        # belirsiz kelimeyi yalnızca adaylarına bakarak seçer.
        context = list(result)
        for token, ascii_word, _cands in pending:
            context[token.start : token.end] = ascii_word
        _apply_tier3_batch(
            result, "".join(context), pending, use_llm=use_llm, model=model
        )
    return "".join(result)


def correct(
    text: str,
    *,
    use_llm: bool = False,
    use_morphology: bool = True,
    model: str | None = None,
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
        model: Tier 3 için kullanılacak Ollama modeli. ``None`` ise
            ``reranker.DEFAULT_MODEL`` (TURKIFY_MODEL env veya yerleşik varsayılan).

    Returns:
        Diakritikleri restore edilmiş metin.
    """
    if not text:
        return text

    spans = protected_spans(text, _protected_words())
    corrected = deasciify(text)
    corrected = restore_spans(corrected, text, spans)

    return _resolve_words(
        text,
        corrected,
        spans,
        use_morphology=use_morphology,
        use_llm=use_llm,
        model=model,
    )
