# Hosted deployment

Rilo supports an optional authenticated hosted mode while keeping local mode as
the default. Hosted mode provides persistent password sessions, CSRF protection,
strict host/origin checks and per-user ownership for evaluations, conversations,
uploads, snapshots, reports, saved suites and user-created agents/tasks.

## Prepare

Copy `.env.example` to `.env.hosted` and set:

```dotenv
RILO_HOSTED=1
RILO_BIND_HOST=0.0.0.0
RILO_PUBLIC_URL=https://rilo.example.com
RILO_ALLOWED_HOSTS=rilo.example.com
RILO_ALLOWED_ORIGINS=https://rilo.example.com
# The example Compose mapping exposes a host-local Bifrost gateway here.
RILO_BIFROST_URL=http://host.docker.internal:8086
RILO_MODEL=ollama/qwen2.5-coder:7b
```

Create the first administrator in the persistent volume before startup:

```sh
docker compose -f docker-compose.hosted.yml run --rm rilo rilo user add \
  --email admin@example.com --name Administrator --admin
docker compose -f docker-compose.hosted.yml up -d --build
```

The compose file binds only to `127.0.0.1:8018`. Put a TLS reverse proxy in front
of it and forward the original host. Do not expose port 8018 directly.

Hosted Rilo accepts Bifrost only at loopback, a literal private IP address or the
explicit Docker host alias; arbitrary DNS names and public destinations remain
rejected. The Compose file maps `host.docker.internal` to Docker's host gateway, so
a host Bifrost can be reached without opening arbitrary Internet inference. Keep
the gateway firewalled to the Rilo host/network. Custom HTTP agents remain strictly
loopback-only and should run as sidecars in the same network namespace.

## Backup, restore and rollback

Stop writes or place the service in maintenance before a backup:

```sh
uv run python scripts/backup.py create --data-dir .rilo --output backups/rilo.tar.gz
uv run python scripts/backup.py restore --archive backups/rilo.tar.gz --destination .rilo-restored
```

The backup uses SQLite's online backup API, copies private objects and stores SHA256
checksums. Restore refuses a non-empty destination and unsafe archive paths.

Tag every deployed image with the Git commit. Rollback by stopping the service,
restoring the pre-deploy archive into a new volume, and starting the previous image.
Schema migrations are additive through version 5, so an older binary should use a
database backup created before the upgrade rather than relying on downgrade logic.

## Operational checks

- `GET /health` is the unauthenticated liveness check.
- Login and a workspace dashboard request are the readiness smoke test.
- Keep `/data` on encrypted persistent storage with restricted backups.
- Terminate TLS at the reverse proxy. Rilo emits HSTS in hosted mode; configure the
  proxy not to strip it and set equivalent policy at the edge if it owns headers.
- Monitor container restarts, HTTP 5xx rates, disk use and worker lease status.
- Create additional users through `POST /api/v1/users` as an administrator.

SQLite remains a single-instance deployment. Run one API/worker container against
one data volume. Move to a shared database and object store before horizontal API
scaling.
