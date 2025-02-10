# MellonPass Server 

MellonPass backend server (GraphQL, docker, database)

## Requirements
- Python 3.11+
- Poetry 1.8+
- Docker 27+

## Running the server
- Run `docker compose build` to build the images.
- Run `docker compose up` to start the database server.

aServer should be running at `http://localhost:8000` and Django admin is accessible via `http://localhost:8000/admin`. See `.django.env` file for a test admin user and test user credentials.

## Development

### Testing

Run tests:

```
docker exec -it mellonpass_server poetry run pytest .
```

### Formatting

Format code:

```
docker exec -it mellonpass_server poetry run ./scripts/dev/autoformat .
```

**Note:** We use black to format code.
