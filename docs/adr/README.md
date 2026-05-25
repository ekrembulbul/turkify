# Mimari Karar Kayıtları (ADR)

Bu klasör, Turkify'ın önemli mimari kararlarını **neden** alındıklarıyla birlikte
kaydeder. Her dosya bir kararı; bağlamını, seçilen yolu, sonuçlarını ve
değerlendirilen alternatifleri içerir.

> ADR nedir? "Architecture Decision Record" — kalıcı, kısa, tarihli karar
> kayıtları. Amaç: ileride "bunu neden böyle yapmışız?" sorusuna net cevap vermek
> ve geri alınan kararların izini tutmak.

## Format
Her ADR: **Durum** (Önerildi / Kabul / Reddedildi / Yerini aldı: …),
**Bağlam**, **Karar**, **Sonuçlar**, **Değerlendirilen alternatifler**.

Karar değişirse eski ADR silinmez; **Durum**'u güncellenir ve yeni ADR'ye atıf
verilir.

## Kayıtlar
| No | Başlık | Durum |
|---|---|---|
| [0001](0001-kademeli-hibrit-mimari.md) | Kademeli (tiered) hibrit düzeltme mimarisi | ✅ Kabul |
| [0002](0002-openai-uyumlu-llm-api.md) | Tier 3 için OpenAI-uyumlu LLM API | ✅ Kabul |
| [0003](0003-native-per-os-gui.md) | Her OS için native frontend | ✅ Kabul |
| [0004](0004-motor-sinir-protokolu.md) | Motor sınır protokolü: tek JSON, stdio + Unix soket | ✅ Kabul |
| [0005](0005-linux-terminal-servis.md) | Linux: terminal + systemd servisi (native GUI yok) | ✅ Kabul |
| [0006](0006-cli-birinci-sinif-kalici.md) | CLI birinci-sınıf ve kalıcı arayüzdür | ✅ Kabul |
| [0007](0007-ayar-saklama-gui-native.md) | Ayar saklama: GUI native, config.json Linux/CLI'ya özgü | ✅ Kabul |
