"""Faz 7 — öğrenen sistem (tercih deposu) testleri.

``isolated_preferences`` fixture'ı (conftest) sayesinde her test geçici bir
depo dosyası kullanır.
"""

from turkify import correct, learn


def test_record_and_get_preference():
    learn.record_preference("ask", "aşk")
    assert learn.get_preference("ask") == "aşk"


def test_preference_lookup_is_turkish_case_insensitive():
    learn.record_preference("ASK", "AŞK")
    assert learn.get_preference("ask") == "aşk"
    assert learn.get_preference("Ask") == "aşk"


def test_unknown_word_has_no_preference():
    assert learn.get_preference("kalem") is None


def test_forget_removes_preference():
    learn.record_preference("ask", "aşk")
    assert learn.forget("ask") is True
    assert learn.get_preference("ask") is None
    assert learn.forget("ask") is False


def test_preference_persists_across_reload(tmp_path):
    path = tmp_path / "prefs.json"
    learn.set_storage_path(path)
    learn.record_preference("ask", "aşk")
    learn.set_storage_path(path)  # önbelleği sıfırlar, dosyadan yeniden okur
    assert learn.get_preference("ask") == "aşk"


def test_preference_overrides_correction_in_engine():
    learn.record_preference("ask", "aşk")
    assert correct("ask") == "aşk"


def test_preference_preserves_word_case_in_engine():
    learn.record_preference("ask", "aşk")
    assert correct("Ask") == "Aşk"
