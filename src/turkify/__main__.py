"""CLI giriş noktası ve komut dağıtımı.

Komutlar:
    python -m turkify [DOSYA] [--no-daemon] [--llm] [--verbose|-v]
        Metni düzeltir. DOSYA verilmezse stdin okunur. Varsayılan olarak
        çalışan daemon'a bağlanmayı dener (hızlı); yoksa in-process düzeltir.
        --verbose: hangi kelimenin hangi katmanda (Tier 2/3) çözüldüğünü
        stderr'e yazar; stdout temiz kalır. Loglar in-process üretildiği için
        --verbose, daemon yerine in-process düzeltmeyi zorlar.
    python -m turkify serve [--llm] [--verbose|-v]
        Kalıcı süreci (daemon) başlatır.

NOT: ``learn`` / ``forget`` komutları Faz 7 (öğrenen sistem) ile birlikte
şimdilik DEVRE DIŞIDIR; ilgili fonksiyonlar aşağıda korunmuştur ama dağıtıma
(``_COMMANDS``) bağlı değildir.

Çıktı sonuna yeni satır eklenmez; girdi yapısı birebir korunur. Hafif komutlar
(daemon istemcisi) ağır motor modüllerini yüklemez.
"""

import logging
import sys

from turkify import server


def _read_input(path: str | None) -> str:
    if path:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    return sys.stdin.read()


def _is_verbose(args: list[str]) -> bool:
    return "--verbose" in args or "-v" in args


def _enable_verbose() -> None:
    """``turkify`` karar günlüğünü stderr'e açar (stdout'a dokunmaz)."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("turkify")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _cmd_correct(args: list[str]) -> int:
    use_llm = "--llm" in args
    no_daemon = "--no-daemon" in args
    verbose = _is_verbose(args)
    if verbose:
        _enable_verbose()

    positionals = [a for a in args if not a.startswith("-")]
    text = _read_input(positionals[0] if positionals else None)

    result = None
    # LLM veya --verbose istenirse daemon'u atla: basit protokol use_llm
    # taşımaz ve karar günlükleri yalnızca in-process süreçte üretilir.
    if not no_daemon and not use_llm and not verbose:
        result = server.correct_via_daemon(text)
    if result is None:
        from turkify.engine import correct

        result = correct(text, use_llm=use_llm)

    sys.stdout.write(result)
    return 0


def _cmd_serve(args: list[str]) -> int:
    if _is_verbose(args):
        _enable_verbose()
    server.serve(use_llm="--llm" in args)
    return 0


# Faz 7 devre dışı: _cmd_learn ve _cmd_forget korunur ama _COMMANDS'a kayıtlı
# değildir. Yeniden etkinleştirmek için aşağıdaki _COMMANDS girdilerini aç.
def _cmd_learn(args: list[str]) -> int:
    if len(args) < 2:
        sys.stderr.write("Kullanım: turkify learn ASCII_KELIME DOGRU_BICIM\n")
        return 2
    from turkify import learn

    learn.record_preference(args[0], args[1])
    return 0


def _cmd_forget(args: list[str]) -> int:
    if not args:
        sys.stderr.write("Kullanım: turkify forget ASCII_KELIME\n")
        return 2
    from turkify import learn

    learn.forget(args[0])
    return 0


_COMMANDS = {
    "serve": _cmd_serve,
    # Faz 7 devre dışı — yeniden açmak için yorumu kaldır:
    # "learn": _cmd_learn,
    # "forget": _cmd_forget,
}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in _COMMANDS:
        return _COMMANDS[args[0]](args[1:])
    return _cmd_correct(args)


if __name__ == "__main__":
    raise SystemExit(main())
