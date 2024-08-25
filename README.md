# MellonPass Server 

MellonPass backend server (GraphQL, docker, database)

## Requirements
- Python 3.11+
- Poetry 1.7.1+
- Docker 20.10.7+

## Installing dependencies
- `poetry install --no-root`

## Running the server
- Use `./script/dev/server/start` to start the Django server.
- Use `docker run --name mellonpass-db --env-file config/envs/.postgres.env -p 5432:5432 -d postgres:15-alpine` to start the database server.

Server is running at `http://127.0.0.1:8000` and Django admin is accessible via `http://127.0.0.1:8000/admin`.

