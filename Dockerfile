ARG PYTHON_VERSION=3.11.10-slim-bullseye
ARG POETRY_VERSION=1.6.1
ARG POETRY_INSTALL_OPTS="--no-root"

# PYTHON BASE
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} as python-base

ARG POETRY_VERSION
ARG POETRY_INSTALL_OPTS

# application code dir
    ENV APP_DIR="code/" \
    # log python output immediately
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    \
    # pip
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # path where app dependencies are installed.
    PYSETUP_PATH="/opt/pysetup" \
    VIRTUAL_ENV="/opt/pysetup/.venv" \
    # poetry
    # https://python-poetry.org/docs/configuration/#using-environment-variables
    POETRY_VERSION=${POETRY_VERSION} \
    # make poetry install to this location
    POETRY_HOME="/opt/poetry" \
    # make poetry create the virtual environment in the project's root
    # it gets named `.venv`
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    # should use the custom virtual env path.
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    POETRY_INSTALL_OPTS=${POETRY_INSTALL_OPTS}

# prepend poetry and venv to path
ENV PATH="$POETRY_HOME/bin:$VIRTUAL_ENV/bin:$PATH"


# DEPENDENCY BUILD STAGE
# ---------------------------------------------------------------------------
FROM python-base as build-stage

WORKDIR ${PYSETUP_PATH}

# Install system dependencies required for psycopg2 and other common packages
RUN apt-get update && apt-get install --no-install-recommends -y \
    # Dependency to install poetry
    curl \
    # Essentials for building python deps
    build-essential \
    # Dependency for psycopg2 
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Download and install poetry based on the POETRY_VERSION and POETRY_HOME envs.
RUN curl -sSL https://install.python-poetry.org | python -

# Copy poetry dependency files
COPY pyproject.toml poetry.lock ./

# Installing dependency on VIRTUAL_ENV
RUN poetry install ${POETRY_INSTALL_OPTS}

# FINAL BUILD STAGE
# ---------------------------------------------------------------------------
FROM python-base as final-build

# Set the working directory inside the container
WORKDIR ${APP_DIR}

# Install system dependencies required for psycopg2 and other common packages
RUN apt-get update && apt-get install --no-install-recommends -y \
    # Essentials for building python deps
    build-essential \
    # Dependency for psycopg2 
    libpq-dev \
    # Remove irrelevat files
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Copy poetry dependency files
COPY pyproject.toml poetry.lock ./

# Copy poetry installed poetry.
COPY --from=build-stage ${POETRY_HOME} ${POETRY_HOME}
COPY --from=build-stage ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Should re-used existing virtual env and installion should be faster.
RUN poetry install ${POETRY_INSTALL_OPTS}

# Copy all files.
COPY . .

# FINAL LOCAL BUILD STAGE
# ---------------------------------------------------------------------------
FROM final-build as local

# Copy django server script.
COPY deploy/dev/start_web /start_web
RUN chmod +x /start_web

# Copy Celery worker script
COPY deploy/dev/start_worker /start_worker
RUN chmod +x /start_worker

# Copy Celery beat script
COPY deploy/dev/start_beat /start_beat
RUN chmod +x /start_beat

# FINAL PRODUCTION BUILD STAGE
# ---------------------------------------------------------------------------
FROM final-build as production

# Copy django server script.
COPY deploy/prod/start_web /start_web
RUN chmod +x /start_web
