all: test

test:
	@pytest -vv --disable-warnings

env:
	@pipenv sync
	@pipenv shell

lock:
	@pipenv lock
	@pipenv lock -r > requirements.txt
	@pipenv lock -r -d > requirements-dev.txt
