.PHONY: install test lint build-index eval run run-mcp

install:
	python -m pip install -U pip
	pip install -r requirements.txt

lint:
	ruff check .

test:
	pytest -q

build-index:
	mkdir -p data/index
	python -m ingest.build_faiss_index --input_dir fixtures/raw --out_dir data/index

eval:
	python -m eval.run_eval --limit 25
	python -m eval.gate --min_recall 0.80 --min_format 0.95 --min_refusal 0.95

run:
	uvicorn app.main:app --reload --port 8000

run-mcp:
	python -m app.mcp_server