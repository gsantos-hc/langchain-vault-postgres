.PHONY: build-wheel build-container build

build-wheel:
	rm -rf dist \
	&& uv build --wheel

build-container:
	docker build -t langchain-vault-demo:latest -f Containerfile .

build: build-wheel build-container
