all: test

env:
	@pipenv sync
	@pipenv shell

test:
	@pytest -vv --disable-warnings
