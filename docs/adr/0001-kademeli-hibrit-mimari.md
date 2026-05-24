# ADR 0001 — Kademeli (tiered) hibrit düzeltme mimarisi

**Durum:** ✅ Kabul (Faz 1–3'te uygulandı)

## Bağlam
Türkçe diakritik (şapka) restorasyonu, ASCII yazılmış metni doğru Türkçe
karakterlere çevirir (`bugun gorusme` → `bugün görüşme`). Bu problem büyük ölçüde
**deterministik** yöntemlerle çözülebilir; literatürde iyi çalışılmıştır. Naif bir
yaklaşım her kelimeyi bir LLM'e sormaktır — ama bu pahalı, yavaş ve "hallucination"
(kelime uydurma) riskli olur.

## Karar
Pahalı LLM'i **varsayılan yol yapma.** Ucuz ve deterministik katmanları önce
çalıştır; LLM'i yalnızca gerçek bağlamsal belirsizliklerde bir *tiebreaker* olarak
kullan. Akış:

1. **Ses uyumu** — soru eki (`mi/mı/mu/mü`) bağlamdan deterministik çözülür.
2. **Tier 1** — Yüret deasciifier (pattern tabanlı), tüm metni hızlıca dönüştürür.
3. **Tier 2** — frekans + zeyrek morfolojik doğrulama; geçersiz/baskın olmayan
   adaylar belirsiz işaretlenir.
4. **Tier 3** — yalnızca belirsiz kelimeler için LLM; **sadece seçer**, metin üretmez.

Korumalı kelimeler, URL/e-posta/sayı/kod ve zaten doğru kelimeler dokunulmadan
bırakılır. Boşluk/noktalama/büyük-küçük harf birebir korunur.

## Sonuçlar
- ✅ Kelimelerin büyük çoğunluğu LLM'siz, deterministik ve hızlı çözülür (< 50 ms).
- ✅ LLM yalnızca seçim yaptığı için **sıfır hallucination** hedefi korunur.
- ✅ Ollama/LLM **opsiyonel**; kapalıyken sistem tam offline çalışır.
- ➖ Katmanlı escalation mantığı (güven/frekans eşikleri) dikkatli ayar ister
  (korpus ASCII-kirliliği için frekans baskınlık faktörü gibi).

## Değerlendirilen alternatifler
- **Her kelimede LLM:** yüksek gecikme + hallucination riski + Ollama zorunlu. Reddedildi.
- **Yalnızca deterministik (LLM yok):** bağlamsal belirsizlikleri (ask/aşk) çözemez.
  Tier 3 opsiyonel eklenerek bu kapatıldı.
