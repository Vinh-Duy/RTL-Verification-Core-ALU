PYTHON ?= python3
SEED ?= 2026
COUNT ?= 1000
TIMEOUT ?= 120
RUN = $(PYTHON) -m verification.run --seed $(SEED) --count $(COUNT) --timeout $(TIMEOUT)

.PHONY: lint test test-random coverage regression mutation exhaustive waveform clean unit examples
lint:
	$(RUN) --mode lint --output results/lint-run
unit:
	$(PYTHON) -m unittest discover -s tests -v
test: unit
	$(RUN) --mode directed --output results/directed
	$(RUN) --mode examples --output results/examples
test-random:
	$(RUN) --mode random --output results/random
coverage:
	$(RUN) --mode coverage --output results/coverage
regression: unit
	$(RUN) --mode regression --output results/regression
mutation:
	$(RUN) --mode mutation --output results/mutation
exhaustive:
	$(RUN) --mode exhaustive --output results/exhaustive
waveform:
	$(RUN) --mode directed --output results/waveform --wave
examples:
	$(RUN) --mode examples --output results/examples
clean:
	$(PYTHON) -c "import shutil; from pathlib import Path; [shutil.rmtree(p) for p in (Path('build'), Path('results')) if p.exists()]"
