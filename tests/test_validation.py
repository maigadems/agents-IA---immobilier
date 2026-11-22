"""Validation humaine : refus par defaut et question groupee du pipeline."""

from agent.tools.validation import Validation, toujours


def compteur(reponse):
    questions = []

    def decideur(action, details):
        questions.append(action)
        return reponse
    return decideur, questions


def test_question_groupee_une_seule_fois():
    decideur, questions = compteur(True)
    v = Validation(decideur)
    with v.accord_groupe("Visite et confirmation", {"bien": "SK-001"},
                         ("Creer une visite dans l'agenda", "Envoyer l'email au client")) as accord:
        assert accord
        assert v.demander("Creer une visite dans l'agenda", {})
        assert v.demander("Envoyer l'email au client", {})
    assert questions == ["Visite et confirmation"]
    assert [e.get("couvert_par") for e in v.journal] == [None, "Visite et confirmation",
                                                         "Visite et confirmation"]


def test_accord_groupe_ne_couvre_chaque_action_qu_une_fois():
    decideur, questions = compteur(False)
    v = Validation(toujours(True))
    with v.accord_groupe("Groupe", {}, ("Envoyer l'email au client",)):
        v.decideur = decideur
        assert v.demander("Envoyer l'email au client", {})       # couverte
        assert not v.demander("Envoyer l'email au client", {})   # seconde fois : on redemande
    assert questions == ["Envoyer l'email au client"]


def test_refus_groupe_ne_couvre_rien():
    decideur, questions = compteur(False)
    v = Validation(decideur)
    with v.accord_groupe("Groupe", {}, ("Creer une visite dans l'agenda",)) as accord:
        assert not accord
        assert not v.demander("Creer une visite dans l'agenda", {})
    assert len(questions) == 2


def test_hors_du_bloc_tout_redevient_soumis():
    decideur, questions = compteur(False)
    v = Validation(toujours(True))
    with v.accord_groupe("Groupe", {}, ("Annuler une visite",)):
        pass
    v.decideur = decideur
    assert not v.demander("Annuler une visite", {})
