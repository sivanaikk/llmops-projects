FROM golang:1.24 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /budgetgate ./cmd/budgetgate

# distroless: no shell, no package manager; the gate only needs to make HTTPS calls.
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /budgetgate /budgetgate
COPY slos /slos
USER nonroot
ENTRYPOINT ["/budgetgate"]
