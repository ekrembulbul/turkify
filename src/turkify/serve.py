"""Motor servisi — sıcak motoru satır-bazlı JSON protokolüyle sunar.

Native frontend'ler (Swift/C#) ve Linux servisi, Python düzeltme motoruyla bu
servis üzerinden konuşur. Motor bir kez yüklenir (zeyrek/frekans sıcak kalır) ve
çok sayıda isteği hızlı işler. Bkz. [ADR 0004](../../docs/adr/0004-motor-sinir-protokolu.md).

Protokol — her satır bir JSON nesnesi:

    istek :  {"id": 1, "text": "bugun gorusme"}
    yanıt :  {"id": 1, "corrected": "bugün görüşme"}
    hata  :  {"id": 1, "error": "..."}
    kontrol: {"cmd": "ping"}   → {"ok": true}
             {"cmd": "reload"} → {"ok": true}   (config.json'u yeniden okur)

İki taşıma (mesaj formatı aynı):
  * ``serve_stdio``  — GUI sahipli (macOS/Windows); stdin EOF'ta temiz çıkar.
  * ``serve_socket`` — bağımsız servis (Linux ``systemd --user``), Unix soketi.

``engine.correct`` aynen kullanılır; bu modül yalnızca ince bir taşıma/protokol
sarmalayıcısıdır. CLI (``turkify``) bundan bağımsızdır ve in-process çalışır
(bkz. [ADR 0006](../../docs/adr/0006-cli-birinci-sinif-kalici.md)).
"""

import json
import logging
import os
import socket
import sys
import time

from turkify import config
from turkify.engine import correct

# Karar/istek günlüğü "turkify" logger'ına yazılır; --verbose ile stderr'e açılır
# (bkz. __main__._enable_verbose). Native GUI bu çıktıyı Log sekmesine düşürür.
_log = logging.getLogger("turkify")

# Loglarda uzun metinleri kısaltma sınırı (satır taşmasını önler).
_LOG_TEXT_LIMIT = 120


def _short(text: str, limit: int = _LOG_TEXT_LIMIT) -> str:
    """Çok satırlı/uzun metni tek satıra indirip kısaltarak repr'ini döner."""
    collapsed = text.replace("\n", " ").replace("\r", " ")
    if len(collapsed) > limit:
        collapsed = collapsed[:limit] + "…"
    return repr(collapsed)


def _resolve_and_apply(overrides: dict | None = None) -> dict:
    """Ayarları öncelikle çözer ve reranker'a uygular; çözülmüş ayarı döner."""
    settings = config.resolve(overrides)
    config.apply(settings)
    return settings


class EngineService:
    """Sıcak motor durumu + istek→yanıt mantığı (taşımadan bağımsız, test edilebilir)."""

    def __init__(self, overrides: dict | None = None, *, settings: dict | None = None):
        self._overrides = overrides or {}
        # ``settings`` testler için enjekte edilebilir; verilmezse config'ten çözülür.
        self._settings = settings if settings is not None else _resolve_and_apply(self._overrides)
        self._log_active("hazir")

    def _log_active(self, phase: str) -> None:
        """Motorun o an etkin ayarlarını (model/katmanlar/sunucu) loglar."""
        s = self._settings
        _log.info(
            "[Motor] %s: model=%r use_llm=%s use_morphology=%s base_url=%s timeout=%ss",
            phase, s.get("model"), s.get("use_llm"), s.get("use_morphology"),
            s.get("base_url"), s.get("timeout"),
        )

    def reload(self) -> None:
        """config.json + env'i yeniden okur (CLI override'ları korunur)."""
        self._settings = _resolve_and_apply(self._overrides)
        self._log_active("yeniden yuklendi")

    def _correct(self, text: str) -> str:
        s = self._settings
        return correct(
            text,
            use_llm=s.get("use_llm", False),
            use_morphology=s.get("use_morphology", True),
            model=s.get("model"),
        )

    def handle(self, request: dict) -> dict:
        """Bir istek nesnesini yanıt nesnesine çevirir (saf; istisna yutmaz-çökmez)."""
        response: dict = {}
        if not isinstance(request, dict):
            return {"error": "istek bir JSON nesnesi olmali"}
        if "id" in request:
            response["id"] = request["id"]

        cmd = request.get("cmd")
        if cmd is not None:
            if cmd == "ping":
                response["ok"] = True
            elif cmd == "reload":
                try:
                    self.reload()
                    response["ok"] = True
                except Exception as exc:  # config bozuksa servis çökmesin
                    response["error"] = f"reload hatasi: {exc}"
            else:
                response["error"] = f"bilinmeyen komut: {cmd!r}"
            return response

        text = request.get("text")
        if text is None:
            response["error"] = "istekte 'text' veya 'cmd' bekleniyor"
            return response
        _log.info("[Istek] alindi: %s", _short(text))
        start = time.perf_counter()
        try:
            corrected = self._correct(text)
        except Exception as exc:  # tek bir düzeltme hatası servisi düşürmesin
            elapsed_ms = (time.perf_counter() - start) * 1000
            _log.info("[Istek] HATA (%.0f ms): %s", elapsed_ms, exc)
            response["error"] = str(exc)
            return response
        elapsed_ms = (time.perf_counter() - start) * 1000
        _log.info("[Istek] tamam (%.0f ms): %s -> %s", elapsed_ms, _short(text), _short(corrected))
        response["corrected"] = corrected
        return response


def _process_line(service: EngineService, line: str) -> dict:
    """Bir JSON satırını çözüp servise verir; bozuk JSON'da hata yanıtı döner."""
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        return {"error": f"gecersiz JSON: {exc}"}
    return service.handle(request)


def _write_response(stream, response: dict) -> None:
    # ensure_ascii=False: Türkçe karakterler ham UTF-8 gider (karşı taraf UTF-8 çözer).
    stream.write(json.dumps(response, ensure_ascii=False) + "\n")
    stream.flush()


def serve_stdio(service: EngineService, *, stdin=None, stdout=None) -> None:
    """stdin'den satır satır okuyup stdout'a yanıt yazar. EOF'ta döner (temiz çıkış)."""
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        _write_response(stdout, _process_line(service, line))


def _handle_connection(service: EngineService, conn: socket.socket) -> None:
    """Tek bir soket bağlantısını satır-bazlı işler (istemci kapatınca biter)."""
    stream = conn.makefile("rw", encoding="utf-8", newline="\n")
    try:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            _write_response(stream, _process_line(service, line))
    finally:
        stream.close()


def serve_socket(service: EngineService, path: str) -> None:
    """Unix soketi dinler; her bağlantıyı sırayla işler. Ctrl-C ile durdurulur."""
    if os.path.exists(path):
        os.unlink(path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen()
    try:
        while True:
            conn, _ = server.accept()
            with conn:
                _handle_connection(service, conn)
    finally:
        server.close()
        if os.path.exists(path):
            os.unlink(path)
