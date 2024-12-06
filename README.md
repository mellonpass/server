# MellonPass Server 

MellonPass backend server (GraphQL, docker, database)

## Requirements
- Python 3.11+
- Poetry 1.7+
- Docker 20+

## Running the server
- Run `docker-compose build` to build the images.
- Run `docker-compose up` to start the database server.

Server should be running at `http://localhost:8000` and Django admin is accessible via `http://localhost:8000/admin`.

## Testing

Use docker container to run tests.

```
docker exec -it mellonpass_server poetry run pytest .
```
