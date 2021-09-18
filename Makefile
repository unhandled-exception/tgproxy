all: test

test:
	@pytest -vv --disable-warnings

env:
	@pipenv shell

lock:
	@pipenv lock
	@pipenv lock -r > requirements.txt
	@pipenv lock -r -d > requirements-dev.txt

actions:
    # https://github.com/nektos/act
	@act -l
	@act
