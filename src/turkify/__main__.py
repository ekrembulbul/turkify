"""CLI giriş noktası ve komut dağıtımı.

Komutlar:
    python -m turkify [DOSYA] [--no-daemon] [--llm]
        Metni düzeltir. DOSYA verilmezse stdin okunur. Varsayılan olarak
        çalışan daemon'a bağlanmayı dener (hızlı); yoksa in-process düzeltir.
    python -m turkify serve [--llm]
        Kalıcı süreci (daemon) başlatır.
    python -m turkify learn ASCII_KELIME DOGRU_BICIM
        Bir kelime için kullanıcı tercihini kaydeder (Faz 7).
    python -m turkify forget ASCII_KELIME
        Bir kelimenin tercihini siler.

Çıktı sonuna yeni satır eklenmez; girdi yapısı birebir korunur. Hafif komutlar
(daemon istemcisi, learn/forget) ağır motor modüllerini yüklemez.
"""

import sys

from turkify import server


def _read_input(path: str | None) -> str:
    if path:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    return sys.stdin.read()


def _cmd_correct(args: list[str]) -> int:
    use_llm = "--llm" in args
    no_daemon = "--no-daemon" in args
    positionals = [a for a in args if not a.startswith("--")]
    text = _read_input(positionals[0] if positionals else None)

    result = None
    # LLM istenirse daemon'u atla (basit protokol use_llm taşımaz).
    if not no_daemon and not use_llm:
        result = server.correct_via_daemon(text)
    if result is None:
        from turkify.engine import correct

        result = correct(text, use_llm=use_llm)

    sys.stdout.write(result)
    return 0


def _cmd_serve(args: list[str]) -> int:
    server.serve(use_llm="--llm" in args)
    return 0


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
    "learn": _cmd_learn,
    "forget": _cmd_forget,
}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in _COMMANDS:
        return _COMMANDS[args[0]](args[1:])
    return _cmd_correct(args)


if __name__ == "__main__":
    raise SystemExit(main())
