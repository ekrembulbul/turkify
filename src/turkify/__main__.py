"""CLI giriş noktası ve komut dağıtımı.

Komutlar:
    python -m turkify [DOSYA] [SECENEKLER]
        Metni düzeltir (in-process). DOSYA verilmezse stdin okunur.
        Ayarlar config'ten okunur; env ve bayraklar onları geçersiz kılar.
        Öncelik: CLI bayrağı > TURKIFY_* env > config > varsayılan.
    python -m turkify agent [SECENEKLER]
        Çok-platform kısayol ajanını başlatır: config'teki kısayolu dinler,
        seçili metni kopyala→düzelt→yapıştır yapar (pynput + pyperclip gerekir).

Tüm config ayarları bayrak olarak verilebilir (hotkey hariç — yapısı bileşik
olduğundan config'ten okunur):
    --model AD             Tier 3 modeli
    --llm / --no-llm       Tier 3'ü aç / kapat
    --morphology /         Tier 2 morfolojiyi aç / kapat
      --no-morphology
    --timeout SN           LLM istek zaman aşımı (saniye)
    --base-url URL         OpenAI-uyumlu sunucu kökü (ör. http://localhost:1234/v1)
    --api-key ANAHTAR      Sunucu API anahtarı
    --llm-options JSON     /chat/completions gövdesine eklenecek JSON (ör. '{"max_tokens":512}')
    --assistant-prefill S  İstek sonuna eklenecek asistan prefill'i; düşünen modellerde
                           reasoning'i atlatmak için $'<think>\\n\\n</think>\\n\\n'
    --verbose | -v         Karar günlüğünü (Tier 2/3) stderr'e yazar; stdout temiz kalır

NOT: ``learn`` / ``forget`` komutları Faz 7 (öğrenen sistem) ile birlikte
şimdilik DEVRE DIŞIDIR; fonksiyonlar korunur ama ``_COMMANDS``'a bağlı değildir.

Çıktı sonuna yeni satır eklenmez; girdi yapısı birebir korunur.
"""

import json
import logging
import sys

from turkify import config


def _force_utf8_io() -> None:
    """stdin/stdout/stderr'i UTF-8'e sabitler.

    Windows'ta akışlar bir konsola değil de boruya/dosyaya yönlendirildiğinde
    Python yerel ANSI kod sayfasına (ör. cp1254) düşer; bu, Türkçe karakterleri
    bozar. macOS/Linux'ta zaten UTF-8 olduğundan bu çağrı etkisizdir.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


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


def _flag_tristate(args: list[str], on: str, off: str) -> bool | None:
    """``--on`` → True, ``--off`` → False, ikisi de yoksa ``None`` (verilmedi)."""
    if off in args:
        return False
    if on in args:
        return True
    return None


def _parse_settings_args(args: list[str]) -> tuple[dict, list[str]]:
    """Ortak ayar bayraklarını ``config.resolve`` override sözlüğüne çevirir.

    Değeri ``None`` olanlar "verilmedi" sayılır; alt katman (env/config) korunur.
    Geçersiz ``--timeout`` / ``--llm-options`` ``ValueError`` yükseltir.

    Returns:
        ``(overrides, remaining)`` — ``remaining`` değer-opsiyonları çıkarılmış
        arg listesidir (bool bayraklar ve konumsal argümanlar kalır).
    """
    overrides: dict = {}
    overrides["model"], args = _extract_opt(args, "--model")
    overrides["base_url"], args = _extract_opt(args, "--base-url")
    overrides["api_key"], args = _extract_opt(args, "--api-key")
    overrides["assistant_prefill"], args = _extract_opt(args, "--assistant-prefill")

    timeout_raw, args = _extract_opt(args, "--timeout")
    overrides["timeout"] = float(timeout_raw) if timeout_raw is not None else None

    options_raw, args = _extract_opt(args, "--llm-options")
    overrides["llm_options"] = json.loads(options_raw) if options_raw is not None else None

    overrides["use_llm"] = _flag_tristate(args, "--llm", "--no-llm")
    overrides["use_morphology"] = _flag_tristate(args, "--morphology", "--no-morphology")
    return overrides, args


def _enable_verbose() -> None:
    """``turkify`` karar günlüğünü stderr'e açar (stdout'a dokunmaz)."""
    handler = logging.StreamHandler(sys.stderr)
    # Agent loglarıyla tutarlı, saliseli öneksiz zaman damgası: "14:03:21.456 [Tier...] ...".
    handler.setFormatter(
        logging.Formatter("%(asctime)s.%(msecs)03d %(message)s", datefmt="%H:%M:%S")
    )
    logger = logging.getLogger("turkify")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _cmd_correct(args: list[str]) -> int:
    if _is_verbose(args):
        _enable_verbose()
    try:
        overrides, remaining = _parse_settings_args(args)
    except (ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"Gecersiz secenek degeri: {exc}\n")
        return 2

    settings = config.resolve(overrides)  # CLI > env > config > varsayilan
    config.apply(settings)

    positionals = [a for a in remaining if not a.startswith("-")]
    text = _read_input(positionals[0] if positionals else None)

    from turkify.engine import correct

    sys.stdout.write(
        correct(
            text,
            use_llm=settings["use_llm"],
            use_morphology=settings["use_morphology"],
            model=settings["model"],
        )
    )
    return 0


def _cmd_agent(args: list[str]) -> int:
    if _is_verbose(args):
        _enable_verbose()
    try:
        overrides, _remaining = _parse_settings_args(args)
    except (ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"Gecersiz secenek degeri: {exc}\n")
        return 2

    settings = config.resolve(overrides)
    from turkify import agent

    agent.run(settings)
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
    _force_utf8_io()
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in _COMMANDS:
        return _COMMANDS[args[0]](args[1:])
    return _cmd_correct(args)


if __name__ == "__main__":
    raise SystemExit(main())
