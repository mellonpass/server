# API Server 

MellonPass backend server (GraphQL, docker, and database)

# Getting started

### Prerequisites

Make sure you have the following installed on your machine:

- [python](https://www.python.org/downloads/) (>= 3.11)
- [poetry](https://python-poetry.org/) (>=1.8)
- [docker](https://www.docker.com/products/docker-desktop/) (>= 27.x)

### Installation

1. Cloning the repository:

    ```
    git clone git@github.com:mellonpass/server.git
    ```

### Running the application

1. Build service images:

    ```
    docker compose build
    ```

1. Starting required services:

    ```
    docker compose up
    ```

- GraphQL server is accessible via `http://localhost:8000/graphql`.
- Django admin is accessible via `http://localhost:8000/admin`. 
    - See `docker-compose.yml` file for a test admin user and test user credentials.

# Development

### Django shell

To access Django shell session:

```
docker exec -it mellonpass_server poetry run python manage.py shell_plus
```

### Testing

To run the tests:

```
docker exec -it mellonpass_server poetry run pytest .
```

### Formatting

To format the codebase:

```
docker exec -it mellonpass_server poetry run ./scripts/dev/autoformat .
```

**Note:** We use black to format code.

### Container session

To get into the container:

```
docker exec -it mellonpass_server bash
```

Then you can run all bash commands inside the container.

# Contributing

To contribute, follow these steps:

- Fork the repository.
- Create a new branch (`git checkout -b feat/your-feature`).
- Make your changes.
- Commit your changes. See [conventional-commits](https://gist.github.com/roelzkie15/3fe7635c542aee64c568535eb8ea25d3) for composing commit messages.
- Push to the branch (`git push origin feat/your-feature`).
- Open a pull request.

# License

This project is licensed under the GPL v3 License. See the [LICENSE](/LICENSE) file for details.
