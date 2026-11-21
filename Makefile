PY ?= python3
BENCH ?=

.PHONY: test demo check live clean

## unit tests + mutant tests for every gate (~1 min)
test:
	$(PY) -m unittest -v tests/test_rtlopt.py

## replay the recorded trajectories on all benchmarks; every verdict is recomputed (~6 min)
demo:
	$(PY) -m rtlopt --backend replay $(if $(BENCH),--bench $(BENCH))

## check that the replay still reproduces the headline gains
check:
	$(PY) scripts/check_results.py

## run the agent live with Claude (needs ANTHROPIC_API_KEY or an `ant auth login` profile)
live:
	$(PY) -m rtlopt --backend claude --max-evals 10 --out results_live $(if $(BENCH),--bench $(BENCH))

clean:
	rm -rf build results results_live tests/__pycache__ rtlopt/__pycache__
