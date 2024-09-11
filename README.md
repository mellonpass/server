# MellonPass Server 

MellonPass backend server (GraphQL, docker, database)

## Requirements
- Python 3.11+
- Poetry 1.7.1+
- Docker 20.10.7+

## Installing dependencies
- `poetry install --no-root`

## Running the server
- Run `docker-compose up` to start the database server.
- Run `poetry shell` to open python virtual environment.
- Run `./script/dev/server/start` to start the Django server.

Server should be running at `http://127.0.0.1:8000` and Django admin is accessible via `http://127.0.0.1:8000/admin`.
