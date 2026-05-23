"""Ses uyumu (soru eki) çözücü testleri."""

from turkify import correct, harmony


# --- harmony.resolve_question_particle ---


def test_front_vowel_gives_mi():
    assert harmony.resolve_question_particle("mi", "geldi") == "mi"


def test_back_vowel_gives_mi_dotless():
    assert harmony.resolve_question_particle("mi", "aldın") == "mı"


def test_rounded_back_gives_mu():
    assert harmony.resolve_question_particle("mu", "oldu") == "mu"


def test_rounded_front_gives_mu_umlaut():
    assert harmony.resolve_question_particle("mu", "gördü") == "mü"


def test_inflected_form_harmonizes():
    assert harmony.resolve_question_particle("misin", "aldın") == "mısın"
    assert harmony.resolve_question_particle("misin", "geldin") == "misin"
    assert harmony.resolve_question_particle("musun", "gördün") == "müsün"


def test_non_particle_returns_none():
    assert harmony.resolve_question_particle("kalem", "geldi") is None


def test_no_previous_word_returns_none():
    assert harmony.resolve_question_particle("mi", None) is None


def test_previous_without_vowel_returns_none():
    assert harmony.resolve_question_particle("mi", "42") is None


def test_collision_word_not_treated_as_particle():
    # "mudur" listede degil (musdur/müdür ile karisir) -> dokunulmaz.
    assert harmony.resolve_question_particle("mudur", "bu") is None


# --- engine entegrasyonu (zeyrek/frekanstan bağımsız: harmony önce çalışır) ---


def test_engine_resolves_particle_by_context():
    # Onceki kelime ince (kale) -> "mi"; kalin (araba) -> "mı".
    assert correct("kale mi") == "kale mi"
    assert correct("araba mi") == "araba mı"
