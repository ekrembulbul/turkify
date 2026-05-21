"""Tier 2 — diakritik aday üretimi.

Bir kelimedeki çevrilebilir her karakter (c/ç, g/ğ, o/ö, s/ş, u/ü, i/ı ve büyük
harf eşleri) iki seçeneğe sahiptir. ``k`` çevrilebilir karakter ``2^k`` aday
üretir; bu yüzden aday sayısı bir üst sınırla (``max_convertible``) tutulur.
Üretilen adaylar kelimenin büyük/küçük harf desenini korur; yalnızca diakritik
farklılaşır.
"""

from itertools import product

# Çevrilebilir karakter → (seçenek1, seçenek2). Hem ASCII hem Türkçe biçim
# aynı seçenek çiftine eşlenir; böylece girdi hangi biçimde olursa olsun
# tüm varyantlar üretilir.
_OPTIONS: dict[str, tuple[str, str]] = {}
for _ascii, _tr in (
    ("c", "ç"),
    ("g", "ğ"),
    ("o", "ö"),
    ("s", "ş"),
    ("u", "ü"),
    ("i", "ı"),
):
    _OPTIONS[_ascii] = (_ascii, _tr)
    _OPTIONS[_tr] = (_ascii, _tr)
for _ascii, _tr in (
    ("C", "Ç"),
    ("G", "Ğ"),
    ("O", "Ö"),
    ("S", "Ş"),
    ("U", "Ü"),
    ("I", "İ"),
):
    _OPTIONS[_ascii] = (_ascii, _tr)
    _OPTIONS[_tr] = (_ascii, _tr)


def is_convertible(char: str) -> bool:
    """Karakterin diakritik açısından çevrilebilir olup olmadığını söyler."""
    return char in _OPTIONS


def generate_candidates(word: str, max_convertible: int = 6) -> list[str]:
    """Kelimenin diakritik varyantlarını üretir (orijinal dahil).

    Args:
        word: Aday üretilecek kelime.
        max_convertible: İzin verilen azami çevrilebilir karakter sayısı.
            Bu sınır aşılırsa aday patlamasını (``2^k``) önlemek için boş
            liste döner.

    Returns:
        Büyük/küçük harf deseni korunmuş aday listesi. Çevrilebilir karakter
        yoksa yalnızca kelimenin kendisini içerir. Sınır aşılırsa boş liste.
    """
    positions = [i for i, ch in enumerate(word) if ch in _OPTIONS]
    if not positions:
        return [word]
    if len(positions) > max_convertible:
        return []

    chars = list(word)
    option_lists = [_OPTIONS[word[i]] for i in positions]
    candidates = []
    for combo in product(*option_lists):
        for pos, choice in zip(positions, combo):
            chars[pos] = choice
        candidates.append("".join(chars))
    return candidates
