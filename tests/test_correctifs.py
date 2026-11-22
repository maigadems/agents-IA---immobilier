"""Activation des correctifs pour comparer avant / apres."""

import pytest

from agent import correctifs


@pytest.fixture(autouse=True)
def registre(monkeypatch):
    monkeypatch.setattr(correctifs, "CORRECTIFS", {"a": "premier", "b": "second"})


def test_tous_par_defaut(monkeypatch):
    monkeypatch.delenv("CORRECTIFS", raising=False)
    assert correctifs.actifs() == {"a", "b"}


def test_aucun(monkeypatch):
    monkeypatch.setenv("CORRECTIFS", "aucun")
    assert not correctifs.est_actif("a")


def test_liste(monkeypatch):
    monkeypatch.setenv("CORRECTIFS", "b")
    assert correctifs.actifs() == {"b"}


def test_nom_inconnu_refuse(monkeypatch):
    monkeypatch.setenv("CORRECTIFS", "z")
    with pytest.raises(ValueError):
        correctifs.actifs()
