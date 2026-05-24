# ADR 0002 — Tier 3 için OpenAI-uyumlu LLM API

**Durum:** ✅ Kabul · Önceki "Ollama'ya özgü API" yaklaşımının yerini aldı

## Bağlam
Tier 3 (LLM rerank) başlangıçta **Ollama'ya özgü** `/api/generate` ucunu ve
Ollama'ya has alanları (`think`, `num_predict`, `options`) kullanıyordu. Bu, yalnızca
Ollama'yı destekliyordu; kullanıcılar LM Studio, llama.cpp, Jan, vLLM, MLX gibi
diğer yerel LLM sunucularını kullanamıyordu.

Neredeyse tüm yerel LLM sunucuları **OpenAI-uyumlu** `/v1/chat/completions` ucunu
sunuyor — Ollama dahil.

## Karar
Taşıma katmanını **OpenAI-uyumlu** `/v1/chat/completions`'a taşı. Aday-seçme ve
ayrıştırma mantığı (backend-bağımsız) aynı kalsın.

- Sunucu adresi `base_url` ile (varsayılan Ollama'nın `…:11434/v1` ucu).
- Opsiyonel `api_key` → `Authorization: Bearer` (yerel sunucular genelde istemez).
- `llm_options` (dict) → istek gövdesine ekstra **alan** olarak eklenir
  (ör. `chat_template_kwargs`); sunucu/model-özel ayarlar Turkify'a gömülmeden yönetilir.
- `max_tokens` tavanı **kaldırıldı**: düşünen modellerde cevabı kesiyordu; güvenlik
  ağı zaten `timeout`.

## Sonuçlar
- ✅ Tek istemci ile Ollama + LM Studio + llama.cpp + Jan + vLLM + MLX desteklenir.
- ✅ Hem yerel (anahtarsız), hem anahtarlı yerel (vLLM), hem uzak OpenAI-uyumlu uç çalışır.
- ➖ Reasoning'i kapatmanın **standart bir yolu yok**; motor başına farklı
  (bkz. [ADR 0004 değil — KURULUM/PORTABILITY "düşünme modu"]). `assistant_prefill`
  ve `llm_options` ile çözülür.
- ➖ Uzak/bulut uç teknik olarak mümkün ama "tamamen yerel" felsefesinden çıkmak demek;
  varsayılan yereldir.

## Değerlendirilen alternatifler
- **Ollama'ya özgü API'de kalmak:** ekosistemin geri kalanını dışlardı. Reddedildi.
- **Her backend için ayrı istemci:** gereksiz bakım; hepsi OpenAI-uyumlu olduğundan gereksiz.
