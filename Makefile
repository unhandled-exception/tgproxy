all: test

run:
	@pipenv run ./tgp.py ${TGPROXY_DEFAULT_CHANNEL}

test:
	@pipenv run pytest -vv --disable-warnings

test-log:
	@pipenv run pytest -vv --disable-warnings --log-level=INFO

cov:
	@pipenv run pytest -vv --disable-warnings --cov=tgproxy --cov-append --cov-report html:coverage_report --cov-report term

env:
	@pipenv shell

lock:
	@pipenv lock
	@pipenv lock -r > requirements.txt
	@pipenv lock -r -d > requirements-dev.txt

act:
#   https://github.com/nektos/act
	@act -l
	@act --rm
