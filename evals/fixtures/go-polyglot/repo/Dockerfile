# syntax=docker/dockerfile:1.7
FROM golang:1.22.5-alpine3.20 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/fleetd ./cmd/fleetd

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/fleetd /fleetd
COPY migrations /migrations
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/fleetd"]
