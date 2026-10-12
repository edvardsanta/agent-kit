PREFIX ?= $(HOME)/.local

.PHONY: install test

install:
	mkdir -p $(PREFIX)/bin
	ln -sf $(CURDIR)/bin/agent-init $(PREFIX)/bin/agent-init

test:
	python3 -m unittest discover -s tests
