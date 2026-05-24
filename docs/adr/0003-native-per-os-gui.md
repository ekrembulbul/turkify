# ADR 0003 — Her OS için native frontend

**Durum:** ✅ Kabul · Önceki "tek çok-platform GUI (Tkinter)" önerisinin yerini aldı

## Bağlam
GUI fazı için önce tek bir çok-platform framework (Tkinter, ya da rumps+pystray)
düşünülmüştü. Ancak:
- macOS izin yönetimi (Input Monitoring + Accessibility / TCC) **zorunlu olarak
  native API** (PyObjC) gerektiriyor — hiçbir çapraz-platform kütüphane düzgün çözmüyor.
- Menü-bar/tray davranışı OS'lar arası çok farklı (macOS menü-bar ≠ Windows tray ≠
  Linux/Wayland).
- `rumps`, SwiftUI'nin native kalitesini vermiyor.

Proje sahibi: native kalite önemli; bakım ve dil farkı kabul edilebilir.

## Karar
**Her OS kendi native dili/araç setiyle bir frontend kullanır.** Çekirdek
düzeltme motoru Python'da paylaşımlı kalır; frontend'ler onunla tanımlı bir
protokol üzerinden konuşur (bkz. [ADR 0004](0004-motor-sinir-protokolu.md)).

| OS | Dil | UI |
|---|---|---|
| macOS | **Swift** | SwiftUI `MenuBarExtra` (menü-bar) |
| Windows | **C# / .NET 8** | **WPF** tray (NotifyIcon) |
| Linux | **Python** | terminal + `systemd --user` servisi (GUI yok) — bkz. [ADR 0005](0005-linux-terminal-servis.md) |

Rol dağılımı: native taraf menü-bar/tray, global kısayol, pano ve izinleri yapar;
Python yalnızca **metin düzeltme** sağlar. Aradan geçen tek şey "metin → düzeltilmiş
metin".

## Sonuçlar
- ✅ Her platformda en iyi native deneyim ve doğru izin/paketleme yolu.
- ✅ Çekirdek motor (zeyrek/deasciifier/reranker) tek yerde, tüm frontend'lerce paylaşılır.
- ➖ Üç ayrı frontend dili (Swift/C#/Python) → daha fazla bakım. (Kabul edildi.)
- ➖ **Python'u her native app'e gömme** maliyeti doğar (bkz. Sonuçlar / paketleme
  fazı): dağıtımda her app'in içine Python çalışma zamanı + bağımlılıklar gerekir
  (yaklaşım: `python-build-standalone`). Geliştirmede sorun değil (yerel venv).
- ➖ Swift/C# için derleme/test, Python dışı araç zinciri (Xcode, .NET SDK) gerektirir.

## Değerlendirilen alternatifler
- **Tek framework (Tkinter / Qt / PySide):** izin sorununu çözmüyor + native kalite düşük. Reddedildi.
- **rumps (macOS Python menü-bar):** hızlı ama SwiftUI kalitesinde değil; native tercih edildi.
- **Tümünü tek dilde (Swift her yerde):** SwiftUI yalnızca Apple; Windows/Linux'ta yok. Reddedildi.
