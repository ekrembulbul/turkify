"""Büyük harf (capitalize) ile koruma etkileşimi (motor seviyesi).

Kural: cümle başı / noktalama sonrası büyük harf yapma, **kullanıcı korumalı
kelimelerinden etkilenmez** (onlar büyütülür); yalnızca yapısal kalıplar
(URL/e-posta/sayı/kod) büyütmeden muaftır.
"""

from turkify.engine import correct


def _protected_file(tmp_path, words: list[str]) -> str:
    path = tmp_path / "protected_words.txt"
    path.write_text("\n".join(words) + "\n", encoding="utf-8")
    return str(path)


def test_korumali_kelime_cumle_basinda_buyutulur(tmp_path):
    pwf = _protected_file(tmp_path, ["falanca"])
    result = correct(
        "falanca geldi. falanca gitti",
        use_morphology=False,
        protected_words_file=pwf,
        capitalize_sentences=True,
        capitalize_first=True,
    )
    assert result == "Falanca geldi. Falanca gitti"


def test_url_ve_eposta_cumle_basinda_buyutulmez(tmp_path):
    pwf = _protected_file(tmp_path, [])
    result = correct(
        "normal cumle. ali@x.com yazdi",
        use_morphology=False,
        protected_words_file=pwf,
        capitalize_sentences=True,
        capitalize_first=True,
    )
    # E-posta yapısal kalıptır; ilk harfi büyütülmez (anlamı bozardı).
    assert "ali@x.com" in result
    assert "Ali@x.com" not in result


def test_korumali_kelime_diakritigi_korunur_ama_cumle_ortasinda_buyutulmez(tmp_path):
    # Korumalı kelime diakritik restorasyonundan muaf kalır ('foo' aynen) ve
    # cümle ortasında olduğundan büyütülmez.
    pwf = _protected_file(tmp_path, ["foo"])
    result = correct(
        "bugun foo kullandim",
        use_morphology=False,
        protected_words_file=pwf,
        capitalize_sentences=True,
    )
    assert "foo" in result
    assert "Foo" not in result
