"""Tier 1 — Deterministik deasciifier sarmalayıcısı.

Vendor edilmiş Yüret algoritmasını (bkz. ``_yuret.py``) temiz bir fonksiyon
arkasına alır. Ham metni olduğu gibi işler: harf pozisyonlarını, boşlukları,
noktalama ve büyük/küçük harf yapısını korur; yalnızca diakritik gerektiren
harfleri yerinde değiştirir. Çıktı, girdiyle aynı uzunluktadır.
"""

from turkify._yuret import Deasciifier


def deasciify(text: str) -> str:
    """ASCII Türkçe metne diakritikleri deterministik olarak geri koyar.

    Args:
        text: ASCII (şapkasız) Türkçe metin.

    Returns:
        Diakritikleri restore edilmiş metin. Girdiyle aynı uzunlukta;
        boşluk, noktalama ve büyük/küçük harf yapısı korunur.
    """
    if not text:
        return text
    return Deasciifier(text).convert_to_turkish()
