# ADR 0006 — CLI birinci-sınıf ve kalıcı arayüzdür

**Durum:** ✅ Kabul

## Bağlam
Faz 6 ile native frontend'ler (Swift/C#) ve bir motor servisi (`turkify serve`)
geliyor. Bu yeni katmanların, mevcut **komut satırı arayüzünü (CLI)** gölgede
bırakması veya ona bağımlı hale getirmesi riski var.

Proje sahibi açıkça belirtti: **CLI temel kullanım senaryosudur ve her zaman
kullanılabilir olmalıdır.**

## Karar
`turkify` CLI'ı (stdin/dosya → düzeltilmiş metin) **birinci-sınıf, birincil ve
kalıcı** arayüz kabul edilir.

- CLI **in-process** çalışır (`engine.correct` doğrudan); `serve`'e, herhangi bir
  servise veya native frontend'e **bağımlı değildir**.
- `serve` ve native frontend'ler CLI'ın **üstüne eklenen** giriş noktalarıdır;
  CLI'ın yerine geçmez.
- [ADR 0003](0003-native-per-os-gui.md)/[0004](0004-motor-sinir-protokolu.md)'teki
  değişiklikler **CLI'ı kapsamaz** — geçici `agent` (kısayol/pano) emekliye ayrıldı
  (kaldırıldı), ama CLI ayrılmaz.
- CLI tüm ayar bayraklarını destekler ve öncelik sırasına uyar (bkz. PORTABILITY §2).

## Sonuçlar
- ✅ Native frontend hiç olmasa bile (ya da bir OS'ta henüz yokken) yazılım CLI ile
  tam işlevseldir; script'lenebilir, pipe'lanabilir, otomasyona uygundur.
- ✅ CLI yolu her zaman test kapsamındadır (regresyon koruması).
- ✅ `engine.correct` hem CLI hem `serve` için tek ortak çekirdek; ikisi de aynı
  davranışı verir.
- ➖ Yeni özellikler eklenirken "CLI'dan da erişilebilir mi?" sorusu her zaman
  gözetilmelidir (ek bir tasarım kısıtı, ama bilinçli).

## Değerlendirilen alternatifler
- **GUI-merkezli olup CLI'ı ikincil/opsiyonel bırakmak:** temel kullanım senaryosu
  CLI olduğundan reddedildi.
- **CLI'ı `serve` üstüne kurmak (CLI → yerel servise konuşur):** gereksiz bağımlılık
  ve gecikme; CLI in-process kalır. Reddedildi.
