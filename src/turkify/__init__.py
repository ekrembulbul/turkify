"""Turkify — Türkçe diakritik (şapka) restorasyon sistemi.

Kademeli (hibrit) mimari:
  Tier 1  deterministik deasciifier  (Faz 1, bu sürüm)
  Tier 2  aday + frekans + morfoloji (Faz 2)
  Tier 3  LLM rerank                 (Faz 3, opsiyonel)
"""

from turkify.engine import correct

__all__ = ["correct"]
__version__ = "0.1.0"
