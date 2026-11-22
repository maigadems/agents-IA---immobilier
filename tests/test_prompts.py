"""Le lexique wolof n'est ajoute au prompt que si le correctif est actif."""

from agent.prompts import prompt_systeme


def test_lexique_wolof_selon_le_correctif(monkeypatch):
    monkeypatch.setenv("CORRECTIFS", "tous")
    assert "dama soxla" in prompt_systeme(avec_gmail=True)
    assert "dama soxla" not in prompt_systeme(avec_gmail=False)
    monkeypatch.setenv("CORRECTIFS", "aucun")
    assert "dama soxla" not in prompt_systeme(avec_gmail=True)
