# Cibles du projet chargelab. Voir docs/decisions.md pour les regles appliquees.
PYTHON ?= .venv/bin/python
DATE ?= $(shell date -u +%Y-%m-%d)

.PHONY: aide collect edition test bilan propre

aide:
	@echo "make collect              une capture dynamique et le statique du jour"
	@echo "make edition DATE=...     reconstruit l'edition d'un jour depuis l'archive"
	@echo "make test                 toutes les suites, couverture comprise"
	@echo "make bilan                couverture reelle de la collecte"

collect:
	$(PYTHON) collect/verifier.py
	$(PYTHON) collect/collecte_dynamique.py
	$(PYTHON) collect/collecte_statique.py

# La reconstruction ne lit que data/collecte : aucune edition passee ne depend
# d'un telechargement frais. L'empreinte affichee en fin de construction doit
# etre la meme d'une execution a l'autre.
edition:
	$(PYTHON) build/edition.py --date $(DATE)

test:
	bash tests/lancer.sh

bilan:
	$(PYTHON) collect/bilan.py $(DEPUIS)

propre:
	rm -rf .coverage __pycache__ */__pycache__
