"""Cümle başı büyük harf — opsiyonel son-işlem (varsayılan kapalı).

Türkçede cümle sonu noktalama (``.``, ``!``, ``?`` ve ``…``) ardından gelen ilk
harf büyük yazılır. Bu modül, açıkça etkinleştirildiğinde bu konumlardaki küçük
harfleri Türkçe-duyarlı biçimde (i→İ, ı→I) büyütür.

Tasarım notları:
  * Yalnızca **noktalama sonrası** büyütür; metnin ilk harfine DOKUNMAZ. Düzeltme
    çoğu kez bir cümlenin ortasından seçilen parça üzerinde çalışır; ilk harfi
    büyütmek o durumda yanlış olurdu.
  * Noktalama ile sonraki harf arasında en az bir boşluk aranır; böylece ondalık
    sayılar (``3.14``) ve boşluksuz noktalı yazımlar bölünmez.
  * Korunan aralıklardaki (URL/e-posta/kod/korumalı kelime) karakterler atlanır.
"""

from turkify.protect import tr_upper

# Cümle sonu noktalama (sonrasında büyük harf beklenir). "..." ardışık nokta ile,
# "…" tek karakter olarak ele alınır.
_SENTENCE_ENDINGS = frozenset(".!?…")

# Cümle başında harften önce gelebilen açılış işaretleri (tırnak/parantez).
_OPENERS = frozenset("\"'“‘«([{")


def _in_protected(index: int, spans: list[tuple[int, int]]) -> bool:
    """``index`` korunan aralıklardan birinin içinde mi?"""
    return any(start <= index < end for start, end in spans)


def capitalize_sentences(text: str, spans: list[tuple[int, int]] | None = None) -> str:
    """Cümle sonu noktalamadan sonraki küçük harfleri büyütür (Türkçe-duyarlı).

    Args:
        text: Düzeltilmiş metin.
        spans: Korunan ``(start, end)`` aralıkları; bu konumlardaki harfler
            büyütülmez. ``None`` ise koruma uygulanmaz.

    Returns:
        Cümle başları büyütülmüş metin. Uzunluk korunur.
    """
    spans = spans or []
    chars = list(text)
    n = len(chars)

    i = 0
    while i < n:
        if chars[i] not in _SENTENCE_ENDINGS:
            i += 1
            continue

        # Ardışık cümle-sonu noktalamayı atla ("?!", "...").
        j = i + 1
        while j < n and chars[j] in _SENTENCE_ENDINGS:
            j += 1

        # Noktalama ile sonraki harf arasında boşluk şart (ondalık/kısaltma değil).
        if j >= n or not chars[j].isspace():
            i = j + 1
            continue

        # Boşlukları ve açılış işaretlerini (tırnak/parantez) geç.
        k = j
        while k < n and chars[k].isspace():
            k += 1
        while k < n and chars[k] in _OPENERS:
            k += 1

        if k < n and not _in_protected(k, spans):
            upper = tr_upper(chars[k])
            # Yalnızca tek karaktere eşlenen küçük harfleri değiştir (uzunluğu koru).
            if len(upper) == 1 and upper != chars[k]:
                chars[k] = upper

        i = k + 1

    return "".join(chars)
