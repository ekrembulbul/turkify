"""Pakete gömülü veri dosyalarına erişim.

Veri dosyaları (frekans listesi, rerank prompt'u) ``turkify`` paketinin içinde
tutulur ve ``importlib.resources`` ile okunur. Bu, üç ortamda da çalışır:
  * editable kurulum (``pip install -e``) — kaynak ağacı yerinde,
  * wheel kurulumu — paket verisi (bkz. pyproject ``package-data``),
  * **donmuş (frozen) uygulama** (PyInstaller) — veri ``--add-data`` ile gömülür.

Eski yöntem (``Path(__file__).parents[2] / "data" / ...``) repo köküne bağlıydı
ve paketlenince/dondurulunca kırılırdı (bkz. ADR 0009).
"""

from importlib.resources import files


def read_text(*parts: str) -> str | None:
    """Pakete gömülü bir metin dosyasını okur; bulunamazsa ``None`` döner.

    Args:
        *parts: Paket köküne göre yol parçaları, ör. ``("data", "tr_frequency.txt")``.

    Returns:
        Dosya içeriği (UTF-8) ya da dosya yoksa ``None``.
    """
    try:
        return files(__package__).joinpath(*parts).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, NotADirectoryError):
        return None
