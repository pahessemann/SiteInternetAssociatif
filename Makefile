PYTHON ?= python

.PHONY: help run init check clean

help:
	@echo "Commandes disponibles :"
	@echo "  make run    - lancer le serveur local"
	@echo "  make init   - initialiser ou migrer la base SQLite"
	@echo "  make check  - verifier la syntaxe Python"
	@echo "  make clean  - supprimer les caches Python"

run:
	$(PYTHON) app.py

init:
	$(PYTHON) -c "import app; app.init_db(); print('Base SQLite prete')"

check:
	$(PYTHON) -m py_compile app.py tools/generate_hero.py

clean:
	powershell -NoProfile -Command "Remove-Item -LiteralPath '__pycache__','tools\\__pycache__' -Recurse -Force -ErrorAction SilentlyContinue"
