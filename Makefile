all: test

.PHONY: test
test:
	@pytest -vv --disable-warnings
