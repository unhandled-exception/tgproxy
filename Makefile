all: test

test:
	@pytest -vv --disable-warnings
