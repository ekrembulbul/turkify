"""PyInstaller giriş noktası — donmuş motor ikilisi (turkify-engine).

`turkify` CLI'ının ``main()``'ini çağırır; ``sys.argv`` aynen geçer. Yani donmuş
``turkify-engine serve --stdio ...``, ``python -m turkify serve ...`` ile birebir
aynı davranır (bkz. ADR 0009).
"""

import sys

from turkify.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
