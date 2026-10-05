.PHONY: test lint build migrate shellcheck

test:
	go test ./...

lint: shellcheck
	golangci-lint run ./...

shellcheck:
	shellcheck deploy/*.sh

build:
	CGO_ENABLED=0 go build -o bin/fleetd ./cmd/fleetd

migrate:
	./deploy/migrate.sh
