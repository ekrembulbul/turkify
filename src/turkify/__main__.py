"""CLI giriş noktası — metni okur, düzeltilmişini stdout'a yazar.

Girdi kaynağı:
  * argüman verilirse o dosyadan (UTF-8) okunur,
  * verilmezse stdin'den okunur.

Hammerspoon katmanı dosya-argümanı biçimini kullanır (kullanıcı metnini
kabukta kaçışlamaktan kaçınmak için). Komut satırından kullanım:

    echo "bugun gorusme" | python -m turkify
    python -m turkify /tmp/secili_metin.txt

Çıktı sonuna yeni satır eklenmez; girdi yapısı birebir korunur.
"""

import sys

from turkify.engine import correct


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        with open(args[0], encoding="utf-8") as handle:
            text = handle.read()
    else:
        text = sys.stdin.read()
    sys.stdout.write(correct(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
