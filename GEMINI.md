# mellonpass-api — Backend Engineering & Agent Rules (GEMINI.md)

GraphQL + REST API for MellonPass. All vault (cipher) and organization operations run through Strawberry GraphQL; authentication, registration, and public-key lookup use Django REST views. Runtime port: `8000` (blue) / `8001` (green).

## Tech Stack

- **Core**: Python 3.11+, Django 4.2, Django REST Framework, Poetry
- **API**: Strawberry GraphQL (`strawberry-graphql ^0.258`) with Relay `GlobalID`s
- **Database**: PostgreSQL 15 (`psycopg2`, `dj-database-url`)
- **Async Tasks & Cron**: Huey (`SqliteHuey` via `/tmp/huey.sqlite`)
- **Cryptography & Hashing**: `Argon2id` (`Argon2PasswordHasher` with `time_cost=10`, `memory_cost=102400`, `parallelism=8`), custom PBKDF2 matching client derivation, `Fernet` (`EncryptedTextField`), and `ES256` (`ECDSA P-256`) JWTs (`PyJWT` + `cryptography`) for email verification only
- **Security & Abuse Prevention**: `django-ratelimit`, `django-ipware` (`get_ip`), Cloudflare Turnstile (`backoff` retries, controlled by `CF_ENABLE_TURNSTILE_INTEGRATION`)
- **Email & Telemetry**: Mailgun via `django-anymail` (console/local backend in dev), Sentry SDK in production

## Essential Commands

### Local Development

Everything runs in Docker Compose. No local Python environment is needed to run the server (only for running tests/linters outside the container):

```sh
docker compose up
# Django Admin: http://localhost:8000/admin/  (admin@example.com / admin)
# GraphQL Playground: http://localhost:8000/graphql  (DEBUG mode only)
```

The dev entrypoint (`deploy/dev/start_web`) automatically waits for PostgreSQL, runs `manage.py migrate`, creates an idempotent superuser, runs `manage.py inituser`, and starts `runserver 0.0.0.0:8000`. Production uses Gunicorn with 3 workers (`deploy/prod/start_web`).

### Testing

Tests require PostgreSQL. `tox.ini` exports all required test environment variables automatically:

```sh
# Full test & lint suite (recommended)
tox

# Single tox environment
tox -e py311

# Targeted pytest runs (requires env vars from tox.ini to be exported)
poetry run pytest mp/apps/authx/tests/test_login_view.py
poetry run pytest mp/apps/cipher/tests/ -k "test_create" -v
poetry run pytest mp/apps/organizations/tests/
```

Tests use `--reuse-db` (`pytest-django`) for faster repeated runs. For GraphQL tests, use `TestClient` / `GraphQLTestClient` in `mp/core/strawberry/test.py` with `login(user)`. Factory Boy factories live in `tests/factories.py` inside each app.

### Code Style, Type Checking & Migrations

- **Ruff** (`line-length = 88`): Linting and formatting (`migrations/` and `tests/` excluded).
- **mypy**: Configured with `django-stubs` and `strawberry.ext.mypy_plugin` (`mypy.ini`; migrations excluded).
- **Pre-commit hooks** (`.pre-commit-config.yaml`): Ruff autoformat + lint, Conventional Commit validation, and migration completeness check.

```sh
# Format and lint
poetry run ./scripts/dev/autoformat .

# Type check
poetry run mypy mp

# Check for ungenerated Django migrations
./scripts/pre-commit/warn_missing_migrations
```

## Architecture & Key Directories

```text
mp/
  apps/
    authx/            # User, RSAOAEPKey, EmailVerificationToken models.
                      # Argon2PasswordHasher (time_cost=10, memory_cost=102400, parallelism=8).
                      # REST views: check-email, create, verify, setup, login, logout, whoami, unlock, public-key.
                      # Huey @on_commit_task: send_account_verification_link_task.
                      # Management command: inituser.
    cipher/           # Polymorphic Cipher (GenericForeignKey) + CipherData subtypes
                      # (CipherLoginData, CipherCardData, CipherDatabaseData, CipherSecureNoteData).
                      # GraphQL queries (cipher, ciphers) & mutations (create, update, updateToDelete, restoreCipherFromDelete).
                      # Huey @db_periodic_task(crontab(minute="0", hour="0")): delete_ciphers_task.
    organizations/    # Organization & OrganizationMember models (Role: OWNER, ADMIN, MEMBER;
                      # Status: INVITED -> ACCEPTED -> CONFIRMED -> REVOKED).
                      # Services: create_organization, invite_user, accept_invite, confirm_member,
                      # revoke_member (with select_for_update() last-owner protection).
                      # GraphQL queries (organizations, organization, organizationMembers, pendingMembers)
                      # & mutations (create, inviteUser, acceptInvite, confirmMember, revokeMember).
  config/
    base.py           # Root settings inherited by all environments.
    local.py          # Development overrides.
    production.py     # Production hardening (secure cookies, Mailgun Anymail, Sentry, Gunicorn).
    test.py           # Test overrides (references tox env vars).
    urls.py           # Mounts /admin/, /accounts/*, and /graphql.
  core/
    management/commands/
      rotate_db_encryption_key.py  # Online batched DB encryption key rotation command.
    model/fields.py   # EncryptedTextField — transparent MultiFernet at-rest encryption layer.
    graphql/
      permissions.py  # IsAuthenticated Strawberry permission class.
    strawberry/
      test.py         # GraphQL integration TestClient.
    utils/ip.py       # get_ip() client IP extractor via django-ipware for ratelimiting.
  graphql/
    schema.py         # Root schema combining Cipher + Organization with QueryDepthLimiter(max_depth=5)
                      # and production NoSchemaIntrospectionCustomRule.
    views.py          # MPGrahpQLView (disables GraphiQL and GET queries in production).
  crypto.py           # Fernet SymmetricEncryption, ECDSA P-256 ES256 JWT generation/verification.
  cloudflare.py       # Cloudflare Turnstile verification with exponential backoff.
  emailing.py         # HTML + plain-text email dispatch via django-anymail / EmailMultiAlternatives.
scripts/
  dev/                # autoformat, check_missing_migrations helpers.
  pre-commit/         # warn_missing_migrations hook.
deploy/
  common/             # Postgres readiness wait, start_huey_consumer.
  dev/                # start_web for local Docker dev.
  prod/               # start_web for Gunicorn production.
```

## API Endpoints

### REST Authentication (`/accounts/*`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/accounts/check-email` | Check email availability/registration status |
| `POST` | `/accounts/create` | Register inactive user (`3/min` per IP, Turnstile, triggers `@on_commit_task` verification email) |
| `POST` | `/accounts/verify` | Verify `ES256` email JWT, sets `user.verified = True` and invalidates prior tokens |
| `POST` | `/accounts/setup` | Complete one-time cryptographic setup (`login_hash`, `PSK`, `RSAOAEPKey`) |
| `POST` | `/accounts/login` | Authenticate with `email` + `login_hash` (`5/min` per email + `5/min` per IP, Turnstile) |
| `POST` | `/accounts/logout` | Destroy server session |
| `GET` | `/accounts/whoami` | Current session auth state and `csrftoken` setup |
| `POST` | `/accounts/unlock` | Re-verify `login_hash` for active session, returns `psk` & encrypted RSA private key |
| `GET` | `/accounts/public-key` | Fetch active user's Base64 RSA-OAEP public key (`?email=...` or `?uuid=...`) |

### GraphQL (`/graphql`)

All vault (`cipher.*`) and organization (`organization.*`) operations execute over `POST /graphql` behind session auth and CSRF validation.

## Coding Standards & Security Invariants

- **`EncryptedTextField` for all sensitive columns**: Any new model field storing client ciphertext, wrapped keys, or sensitive metadata must use `mp.core.model.fields.EncryptedTextField`.
- **Zero-downtime DB key rotation (`DB_SYMMETRIC_KEYS` / `DB_SYMMETRIC_KEY`)**: `EncryptedTextField` uses a cached `MultiFernet` backed by `settings.DB_SYMMETRIC_KEYS` (index `0` is the active write key; trailing keys remain accepted for reads, and `DB_SYMMETRIC_KEY` remains supported for single-key setups). Never remove a retired key from `DB_SYMMETRIC_KEYS` without completing an online rotation across all existing rows (`python manage.py rotate_db_encryption_key`).
- **Never expose other members' keys**: `OrganizationMember.protected_symmetric_key` must only be returned by GraphQL when `self.user.id == request.user.uuid`.
- **Protect the last owner**: Organization member revocation must acquire row locks via `select_for_update()` and forbid revoking the last `CONFIRMED OWNER`.
- **Enforce auth, CSRF, and GraphQL limits**: Keep `IsAuthenticated` on all GraphQL queries/mutations, `@csrf_protect` and `@ratelimit` on mutating REST views, `QueryDepthLimiter(max_depth=5)`, and production `NoSchemaIntrospectionCustomRule`.
- **Match client KDF parameters**: Server verification and seed utilities must remain aligned with the client's 720,000 PBKDF2 iterations and `Argon2PasswordHasher` (`time_cost=10`).
- **Soft-delete lifecycle**: Do not hard-delete active ciphers directly in standard UX flows; soft-delete sets `delete_on = now + 30 days` so `delete_ciphers_task` handles permanent cleanup.
- **Test coverage required**: Add `pytest` + `FactoryBoy` tests for all new domain services, REST views, and GraphQL resolvers.

### Zero-Downtime DB Encryption Key Rotation Runbook

Follow these steps whenever rotating `DB_SYMMETRIC_KEY` / `DB_SYMMETRIC_KEYS` in production without downtime:

1. **Generate a new Fernet key**:
   ```sh
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
2. **Prepend the new key at index `0` of `DB_SYMMETRIC_KEYS` and deploy**:
   Set `DB_SYMMETRIC_KEYS="<new_key>,<old_key>"` in the environment and roll the application containers. All new writes encrypt with `<new_key>`, while existing rows encrypted under `<old_key>` remain readable.
3. **Dry-run and rotate all existing rows in batches**:
   ```sh
   python manage.py rotate_db_encryption_key --dry-run
   python manage.py rotate_db_encryption_key --batch-size 500
   ```
   This verifies round-trip encryption/decryption and re-encrypts every `EncryptedTextField` column across `User`, `RSAOAEPKey`, `OrganizationMember`, `Cipher`, `CipherLoginData`, `CipherCardData`, `CipherSecureNoteData`, and `CipherDatabaseData`.
4. **Remove the retired key and redeploy**:
   Update `DB_SYMMETRIC_KEYS="<new_key>"` (removing `<old_key>`, and updating `DB_SYMMETRIC_KEY` if still defined) and deploy.
