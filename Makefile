all: test

test: sync
	@pipenv run pytest -vv

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
	@pipenv lock -r > requirements.txt
	@pipenv lock -r -d > requirements-dev.txt

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
