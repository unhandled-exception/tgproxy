all: test

test: sync
	@pipenv run pytest -vv

lint: sync
	@pip install flake8 isort mypy
	@echo "Run flake8"
	@flake8 . --count --show-source --statistics --max-complexity=10 --show-source
	@echo "Run isort checks"
	@isort . -c --diff

test-log: sync
	@pipenv run pytest -vv --log-level=INFO

cov: sync
	@pipenv run pytest -vv --cov=tgproxy --cov-report html:coverage_report --cov-report term

env:
	@pipenv shell

sync:
	@pipenv sync -d

lock:
	@pipenv lock
	@pipenv requirements > requirements.txt
	@pipenv requirements --dev > requirements-dev.txt

docker-build: lock
	docker build . -t tgproxy:latest

act:
#   https://github.com/nektos/act
	@act -l
	@act --rm -j tests -j docker-build

pre-commit:
	@pre-commit run -a

pc-install:
	@pre-commit install

upgrade:
	@pipenv update --outdated -d
