"""Koruma katmanı — diakritik dönüşümünden muaf tutulacak metin aralıkları.

Aşağıdakiler dokunulmadan bırakılır:
  * URL, e-posta, sayı veya kod karakteri içeren boşluksuz parçalar (chunk),
  * korumalı kelime listesindeki yabancı/teknik terimler,
  * zaten Türkçe karakter içeren (muhtemelen doğru yazılmış) kelimeler.

Çıktı, orijinal metindeki ``(start, end)`` karakter aralıklarıdır; bu aralıklar
düzeltme sonrası orijinal hâline geri yazılır (bkz. ``reconstruct``).
"""

import re
from pathlib import Path

from turkify.tokenizer import tokenize

_TURKISH_CHARS = frozenset("çğıöşüÇĞİÖŞÜ")
_CHUNK_RE = re.compile(r"\S+")
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_DIGIT_RE = re.compile(r"\d")
_CODE_CHAR_RE = re.compile(r"[_/\\<>{}()=]")


def tr_lower(text: str) -> str:
    """Türkçe locale kurallarına göre küçük harfe çevirir (I→ı, İ→i)."""
    return text.replace("I", "ı").replace("İ", "i").lower()


def load_protected_words(path: Path | str | None = None) -> frozenset[str]:
    """Korumalı kelime listesini bir dosyadan yükler (Türkçe küçük harfe normalize).

    Yalnızca verilen dosya okunur; paketle gelen ``protected_words.example.txt``
    **otomatik yüklenmez** (yalnızca kopyalanacak bir örnektir — bkz. ADR 0008).

    Args:
        path: Liste dosyası yolu. ``None`` ya da dosya yoksa boş küme döner
            (kelime-listesi koruması opsiyoneldir; URL/e-posta/sayı/Türkçe-karakter
            koruması yine de uygulanır).

    Returns:
        Türkçe küçük harfe çevrilmiş korumalı kelimeler kümesi.
    """
    if path is None:
        return frozenset()
    file_path = Path(path)
    if not file_path.exists():
        return frozenset()

    words = set()
    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        words.add(tr_lower(line))
    return frozenset(words)


def _is_whole_chunk_protected(chunk: str) -> bool:
    """Parçanın tamamı (URL/e-posta/sayı/kod) korunmalı mı?"""
    return bool(
        _URL_RE.search(chunk)
        or _EMAIL_RE.search(chunk)
        or _DIGIT_RE.search(chunk)
        or _CODE_CHAR_RE.search(chunk)
    )


def _is_word_protected(word: str, protected_words: frozenset[str]) -> bool:
    """Tek bir kelime korunmalı mı? (liste üyesi veya zaten Türkçe karakterli)"""
    if any(ch in _TURKISH_CHARS for ch in word):
        return True
    return tr_lower(word) in protected_words


def protected_spans(
    text: str, protected_words: frozenset[str]
) -> list[tuple[int, int]]:
    """Korunması gereken karakter aralıklarını hesaplar.

    Args:
        text: Orijinal (işlenmemiş) metin.
        protected_words: Türkçe küçük harfe normalize edilmiş korumalı kelimeler.

    Returns:
        Çakışmayan, artan sıralı ``(start, end)`` aralıkları listesi.
    """
    spans: list[tuple[int, int]] = []
    for chunk_match in _CHUNK_RE.finditer(text):
        chunk = chunk_match.group()
        chunk_start = chunk_match.start()

        if _is_whole_chunk_protected(chunk):
            spans.append((chunk_start, chunk_match.end()))
            continue

        for token in tokenize(chunk):
            if token.is_word and _is_word_protected(token.text, protected_words):
                spans.append((chunk_start + token.start, chunk_start + token.end))

    return spans
