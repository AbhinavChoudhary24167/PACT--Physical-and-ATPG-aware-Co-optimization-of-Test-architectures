.PHONY: test doctor versions
test:
	python3 -m pytest -q
doctor:
	python3 -m pact.cli doctor
versions:
	./scripts/collect_versions.sh
