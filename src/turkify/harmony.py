"""Türkçe ses uyumu (vowel harmony) ile bağlamsal klitik çözümü.

Soru eki (``mi/mı/mu/mü`` ve çekimli biçimleri) bağımsız bir kelimedir ve doğru
biçimi **önceki kelimenin son ünlüsüne** göre belirlenir — bu rastgele bağlam
değil, kesin bir dilbilgisi kuralıdır:

    önceki son ünlü ince (e, i, ö, ü)  → i / ü   (ör. "geldi mi", "gördü mü")
    önceki son ünlü kalın (a, ı, o, u) → ı / u   (ör. "aldın mı", "oldu mu")

Bu yüzden soru eki, frekans veya LLM yerine **deterministik** olarak çözülür:
hem her zaman doğru hem de bedava. (Anlamsal belirsizlikler — ask/aşk gibi —
yine LLM'e kalır.)
"""

from turkify.protect import tr_lower

_FRONT_VOWELS = frozenset("eiöü")  # ince ünlüler
_BACK_VOWELS = frozenset("aıou")  # kalın ünlüler
_HIGH_VOWELS = frozenset("iıuü")  # dar ünlüler (soru ekinde değişenler)

# Soru ekinin ASCII (kullanıcının yazdığı) biçimleri. Yalnızca gerçek bir
# kelimeyle ÇAKIŞMAYANLAR listelenir; ör. "mudur"/"midir" dışarıda bırakıldı
# çünkü "müdür" (yönetici) ile karışır — onlar frekans/LLM'e bırakılır.
_QUESTION_PARTICLES = frozenset({
    "mi", "mu",
    "miyim", "muyum", "miyiz", "muyuz",
    "misin", "musun", "misiniz", "musunuz",
    "miydi", "muydu", "miymis", "muymus",
})


def _last_vowel_is_front(word: str) -> bool | None:
    """Kelimenin son ünlüsü ince mi? İnce→True, kalın→False, ünlü yoksa None."""
    for char in reversed(word):
        low = tr_lower(char)
        if low in _FRONT_VOWELS:
            return True
        if low in _BACK_VOWELS:
            return False
    return None


def resolve_question_particle(ascii_word: str, previous_word: str | None) -> str | None:
    """Soru eki klitiğini ses uyumuna göre doğru biçimine çevirir.

    Args:
        ascii_word: Kullanıcının yazdığı (ASCII) kelime.
        previous_word: Hemen önceki (düzeltilmiş) kelime; ses uyumu kaynağı.

    Returns:
        Uyumlanmış biçim; kelime bir soru eki değilse veya önceki kelimeden
        karar verilemiyorsa (ör. ünlü yok) ``None``.
    """
    if not previous_word or tr_lower(ascii_word) not in _QUESTION_PARTICLES:
        return None
    front = _last_vowel_is_front(previous_word)
    if front is None:  # önceki kelimede ünlü yok (sayı/kısaltma) → karar verme
        return None

    result = []
    for char in ascii_word:
        low = char.lower()
        if low in _HIGH_VOWELS:
            rounded = low in ("u", "ü")  # ASCII'deki yuvarlaklığı koru
            if rounded:
                result.append("ü" if front else "u")
            else:
                result.append("i" if front else "ı")
        else:
            result.append(char)
    return "".join(result)
