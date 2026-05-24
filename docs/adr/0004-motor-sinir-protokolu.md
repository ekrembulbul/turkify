# ADR 0004 — Motor sınır protokolü: tek JSON, stdio + Unix soket taşıma

**Durum:** ✅ Kabul · Daha önce kaldırılan "daemon" kararını gerekçeli biçimde revize eder

## Bağlam
[ADR 0003](0003-native-per-os-gui.md) ile frontend'ler farklı dillerde (Swift, C#,
Python). Native taraf, Python düzeltme motoruyla konuşmak zorunda. Etkileşim çok
basit: **"metin gir → düzeltilmiş metin çık"** + birkaç kontrol mesajı.

Daha önce bir "daemon" (Unix soketi) vardı ve kaldırılmıştı; gerekçe "ajan motoru
sıcak tuttuğu için ayrı daemon'a gerek yok" idi. Ama artık frontend farklı bir dilde
olduğundan motoru o dilden sıcak tutmanın tek yolu ayrı bir süreç + IPC.

## Karar
**Tek bir satır-bazlı JSON protokolü**, iki taşıma ile (`turkify serve`):

```
istek :  {"id": 1, "text": "bugun gorusme"}
yanıt :  {"id": 1, "corrected": "bugün görüşme"}
hata  :  {"id": 1, "error": "..."}
kontrol: {"cmd": "ping"} → {"ok": true}
         {"cmd": "reload"}  (config.json değişince motor yeniden okur)
```

- **stdio taşıması** (`serve --stdio`): GUI sahipli (macOS/Windows). GUI süreci
  motoru çocuk olarak başlatır, sıcak tutar; GUI ölünce stdin EOF → motor temiz çıkar.
- **Unix soket taşıması** (`serve --socket PATH`): bağımsız servis (Linux systemd).
  Mesaj formatı **birebir aynı**, yalnızca kapı farklı.

Motor başlangıçta `config.resolve()` ile ayarları okur; `reload` ile yeniden okur.

## Sonuçlar
- ✅ Sıcak motor (zeyrek bir kez yüklenir), düşük gecikme.
- ✅ stdio her OS'ta aynı (named-pipe/soket ayrımı yok); hiç ağ yüzeyi yok.
- ✅ Tek protokol → üç frontend ortak sözleşmeyi konuşur.
- ➖ Bu, eskiden kaldırılan daemon'u geri getirir — ama artık **gerekçeli** (farklı
  dilde frontend). Karar bilinçli revize edildi.
- ➖ stdio curl'le test edilemez; ama `echo … | turkify serve` ile elle test edilebilir.

## Değerlendirilen alternatifler
- **Yerel HTTP:** curl-dostu ama port yönetimi + yerel ağ yüzeyi + orphan riski. Birden
  çok bağımsız istemci gerekseydi seçilirdi; gerekmiyor. (İkinci tercih olarak kaldı.)
- **Sadece Unix soket / named pipe:** Windows'ta named pipe ayrımı → fazladan kod;
  daha önce AF_UNIX yol-uzunluğu derdi yaşandı. stdio tercih edildi (Linux servis için soket).
- **gRPC:** "metin → metin" için aşırı; protobuf/codegen yükü. Reddedildi.
- **Her çağrıda CLI (cold start):** basit ama her seferinde Python+zeyrek soğuk başlar, yavaş. Reddedildi.
- **Python'u native sürece gömme (PythonKit/Python.NET):** kırılgan, OS-başına gömme derdi. Reddedildi.
