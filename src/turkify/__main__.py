"""CLI giriş noktası ve komut dağıtımı.

Komutlar:
    python -m turkify [DOSYA] [--llm] [--verbose|-v] [--model AD]
        Metni düzeltir (in-process). DOSYA verilmezse stdin okunur.
        Ayarlar config'ten okunur; bayraklar/env onları geçersiz kılar.
        Öncelik: CLI bayrağı > TURKIFY_* env > config > varsayılan.
        --verbose: hangi kelimenin hangi katmanda (Tier 2/3) çözüldüğünü stderr'e
        yazar; stdout temiz kalır.
        --model AD: Tier 3 modeli (config'teki modeli geçersiz kılar).
    python -m turkify agent [--verbose|-v]
        Çok-platform kısayol ajanını başlatır: config'teki kısayolu dinler,
        seçili metni kopyala→düzelt→yapıştır yapar (pynput + pyperclip gerekir).

NOT: ``learn`` / ``forget`` komutları Faz 7 (öğrenen sistem) ile birlikte
şimdilik DEVRE DIŞIDIR; fonksiyonlar korunur ama ``_COMMANDS``'a bağlı değildir.

Çıktı sonuna yeni satır eklenmez; girdi yapısı birebir korunur.
"""

import logging
import os
import sys

from turkify import config


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
    model_flag, args = _extract_opt(args, "--model")
    use_llm_flag = "--llm" in args
    if _is_verbose(args):
        _enable_verbose()

    cfg = config.load()
    config.apply(cfg)
    # Öncelik: bayrak > env > config.
    model = model_flag or os.environ.get("TURKIFY_MODEL") or cfg["model"]
    use_llm = use_llm_flag or cfg["use_llm"]
    use_morphology = cfg["use_morphology"]

    positionals = [a for a in args if not a.startswith("-")]
    text = _read_input(positionals[0] if positionals else None)

    from turkify.engine import correct

    sys.stdout.write(
        correct(text, use_llm=use_llm, use_morphology=use_morphology, model=model)
    )
    return 0


def _cmd_agent(args: list[str]) -> int:
    if _is_verbose(args):
        _enable_verbose()
    from turkify import agent

    agent.run()
    return 0


# Faz 7 devre dışı: _cmd_learn ve _cmd_forget korunur ama _COMMANDS'a kayıtlı değildir.
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
    "agent": _cmd_agent,
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
