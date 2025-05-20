.PHONY: build

build-wheel:
	rm -rf dist \
	&& uv build --wheel

build-container:
	uv export --quiet --no-dev --no-emit-project --output-file requirements.txt \
	&& docker build -t langchain-vault-demo:latest -f Containerfile .

build-psql:
	docker build -t langchain-vault-demo-psql:latest -f postgres/Containerfile postgres

build: build-wheel build-container build-psql
