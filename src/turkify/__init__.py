"""Turkify — Türkçe diakritik (şapka) restorasyon sistemi.

Kademeli (hibrit) mimari:
  Tier 1  deterministik deasciifier  (Faz 1)
  Tier 2  morfolojik doğrulama       (Faz 2, opsiyonel zeyrek)
  Tier 3  LLM rerank                 (Faz 3, opsiyonel Ollama)
  + Faz 7 lokal öğrenen tercih katmanı

``correct`` tembel içe aktarılır (PEP 562); böylece yalnızca soket istemcisi
gibi hafif kullanımlar ağır motor modüllerini yüklemez.
"""

__all__ = ["correct"]
__version__ = "0.1.0"


def __getattr__(name):
    if name == "correct":
        from turkify.engine import correct

        return correct
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
