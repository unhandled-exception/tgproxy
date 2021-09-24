all: test

test: sync
	@pipenv run pytest -vv --disable-warnings

test-log: sync
	@pipenv run pytest -vv --disable-warnings --log-level=INFO

cov: sync
	@pipenv run pytest -vv --disable-warnings --cov=tgproxy --cov-report html:coverage_report --cov-report term

env:
	@pipenv shell

sync:
	@pipenv sync -d

lock:
	@pipenv lock
	@pipenv lock -r > requirements.txt
	@pipenv lock -r -d > requirements-dev.txt

build: lock
	docker build . -t tgproxy:latest

act:
#   https://github.com/nektos/act
	@act -l
	@act --rm
