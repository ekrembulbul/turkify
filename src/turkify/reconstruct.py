"""Cümle yeniden kurma — korunan aralıkları orijinal hâline geri yazar.

Tier 1 deasciifier metnin uzunluğunu, boşluk/noktalama ve büyük/küçük harf
yapısını zaten korur (yalnızca diakritik harfleri yerinde değiştirir). Bu yüzden
yeniden kurma, düzeltilmiş çıktıdaki korunan aralıkları orijinal karakterlerle
değiştirmekten ibarettir. Düzeltilmiş metin ile orijinal aynı uzunlukta olmalıdır.
"""


def restore_spans(
    corrected: str, original: str, spans: list[tuple[int, int]]
) -> str:
    """Düzeltilmiş metindeki korunan aralıkları orijinaliyle değiştirir.

    Args:
        corrected: Diakritik uygulanmış metin (orijinalle aynı uzunlukta).
        original: İşlenmemiş orijinal metin.
        spans: Geri yazılacak ``(start, end)`` aralıkları.

    Returns:
        Korunan aralıkları orijinal, geri kalanı düzeltilmiş olan metin.

    Raises:
        ValueError: ``corrected`` ile ``original`` uzunlukları eşit değilse.
    """
    if len(corrected) != len(original):
        raise ValueError(
            "Düzeltilmiş metin ile orijinal uzunlukları farklı: "
            f"{len(corrected)} != {len(original)}. "
            "Tier 1 deasciifier uzunluğu korumalıdır."
        )
    if not spans:
        return corrected

    result = list(corrected)
    for start, end in spans:
        result[start:end] = original[start:end]
    return "".join(result)
