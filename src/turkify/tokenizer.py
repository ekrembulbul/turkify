"""Metni kelime ve ayraç (boşluk/noktalama) token'larına böler.

Her token, orijinal metindeki konumunu (``start``/``end``) taşır; böylece
işlenen çıktı, orijinal yapı birebir korunarak yeniden kurulabilir.
Token'ları sırayla birleştirmek daima orijinal metni verir (kayıpsız).
"""

import re
from dataclasses import dataclass

# Kelime = harf/rakam dizisi (Türkçe harfler dahil), alt çizgi hariç.
# Alt çizgi kasıtlı olarak ayraçtır; kod/teknik token tespitine bırakılır.
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass(frozen=True)
class Token:
    """Metnin bir parçası ve orijinaldeki konumu."""

    text: str
    start: int
    end: int
    is_word: bool


def tokenize(text: str) -> list[Token]:
    """Metni sıralı kelime ve ayraç token'larına böler (kayıpsız).

    Args:
        text: Bölünecek metin.

    Returns:
        ``Token`` listesi. ``is_word=True`` olanlar harf/rakam dizileri,
        ``False`` olanlar boşluk/noktalama dizileridir. Token metinleri
        sırayla birleştirildiğinde orijinal metin elde edilir.
    """
    tokens: list[Token] = []
    cursor = 0
    for match in _WORD_RE.finditer(text):
        start, end = match.start(), match.end()
        if start > cursor:
            tokens.append(Token(text[cursor:start], cursor, start, is_word=False))
        tokens.append(Token(match.group(), start, end, is_word=True))
        cursor = end
    if cursor < len(text):
        tokens.append(Token(text[cursor:], cursor, len(text), is_word=False))
    return tokens
