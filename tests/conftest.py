"""Ortak test fixture'ları.

Öğrenen sistem (Faz 7) tercih deposunu her test için geçici bir dosyaya
yönlendirir; böylece testler kullanıcının gerçek ``cache/preferences.json``
dosyasını kirletmez ve birbirinden izole çalışır.
"""

import pytest

from turkify import learn


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path):
    learn.set_storage_path(tmp_path / "preferences.json")
    yield
    learn.set_storage_path(learn._DEFAULT_PATH)
