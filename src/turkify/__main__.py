"""CLI giriş noktası ve komut dağıtımı.

Komutlar:
    python -m turkify [DOSYA] [--no-daemon] [--llm] [--verbose|-v] [--model AD]
        Metni düzeltir. DOSYA verilmezse stdin okunur. Varsayılan olarak
        çalışan daemon'a bağlanmayı dener (hızlı); yoksa in-process düzeltir.
        --verbose: hangi kelimenin hangi katmanda (Tier 2/3) çözüldüğünü
        stderr'e yazar; stdout temiz kalır. Loglar in-process üretildiği için
        --verbose, daemon yerine in-process düzeltmeyi zorlar.
        --model AD: Tier 3 için Ollama modeli (ör. qwen2.5:32b). TURKIFY_MODEL
        ortam değişkeniyle de ayarlanabilir. --model in-process düzeltmeyi zorlar.
    python -m turkify serve [--llm] [--verbose|-v] [--model AD]
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


def _extract_opt(args: list[str], name: str) -> tuple[str | None, list[str]]:
    """``--name DEGER`` varsa DEĞER'i ve onu çıkarılmış arg listesini döner."""
    if name in args:
        index = args.index(name)
        value = args[index + 1] if index + 1 < len(args) else None
        return value, args[:index] + args[index + 2 :]
    return None, args


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
    model, args = _extract_opt(args, "--model")
    use_llm = "--llm" in args
    no_daemon = "--no-daemon" in args
    verbose = _is_verbose(args)
    if verbose:
        _enable_verbose()

    positionals = [a for a in args if not a.startswith("-")]
    text = _read_input(positionals[0] if positionals else None)

    result = None
    # LLM/--verbose/--model istenirse daemon'u atla: basit protokol bunları
    # taşımaz ve karar günlükleri yalnızca in-process süreçte üretilir.
    if not no_daemon and not use_llm and not verbose and model is None:
        result = server.correct_via_daemon(text)
    if result is None:
        from turkify.engine import correct

        result = correct(text, use_llm=use_llm, model=model)

    sys.stdout.write(result)
    return 0


def _cmd_serve(args: list[str]) -> int:
    model, args = _extract_opt(args, "--model")
    if _is_verbose(args):
        _enable_verbose()
    server.serve(use_llm="--llm" in args, model=model)
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
