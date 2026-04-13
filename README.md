# CulinaryGraph

A region-aware recipe sharing platform built with Django and MySQL for the SWE573
Software Development Practice course. This document is a step-by-step guide to
building, running, and deploying the project — written so that a developer fluent
with common tools but unfamiliar with Docker or this codebase can get it running
from scratch.

- **Live service:** https://culinary-service-727322696060.europe-west10.run.app/
- **Wiki:** [GitHub Wiki](https://github.com/Erotgen/2024719141-SWE-573-Software-Development-Practice/wiki)

---

## Table of contents

1. [Requirements](#1-requirements)
2. [Get the code](#2-get-the-code)
3. [Environment variables](#3-environment-variables)
4. [Run it (three options)](#4-run-it)
5. [Verify it's working](#5-verify-its-working)
6. [Deploy to Google Cloud Run](#6-deploy-to-google-cloud-run-production)
---

## 1. Requirements

Install the tools and follow the instructions.                          |


---

## 2. Get the code

```bash
git clone https://github.com/Erotgen/2024719141-SWE-573-Software-Development-Practice.git
cd 2024719141-SWE-573-Software-Development-Practice
```

All commands below assume your shell is in the project root — the folder that
contains `Dockerfile`, `manage.py`, and `settings.py`.

---

## 3. Environment variables

The app reads configuration from environment variables. At startup, [settings.py](settings.py)
also loads a `.env` file sitting next to it (a 12-line inline parser — no extra
dependency), so the easiest thing for local dev is to drop a `.env` file in the
project root.

Copy the template:
```bash
copy .env.example .env      # Windows CMD
```

Then edit `.env`. Every variable and what it does:

| Variable        | Required?     | Example                                       | What it does                                                                                            |
|-----------------|---------------|-----------------------------------------------|---------------------------------------------------------------------------------------------------------|
| `SECRET_KEY`    | yes (in prod) | `a-long-random-string`                        | Django signing key used for sessions and CSRF. In production, set a real random value.                 |
| `DEBUG`         | no            | `1` (dev) / `0` (prod)                        | `1` enables Django debug mode (stack traces, auto-reload). Default `1`.                                 |
| `ALLOWED_HOSTS` | no (dev)      | `*` or `mysite.com,api.mysite.com`            | Comma-separated list of hostnames Django will answer requests for. Default `*`.                        |
| `DB_NAME`       | yes           | `CulinaryGraph`                               | MySQL database name.                                                                                    |
| `DB_USER`       | yes           | `root`                                        | MySQL user.                                                                                             |
| `DB_PASSWORD`   | yes           | `your-password`                               | MySQL user password.                                                                                    |
| `DB_HOST`       | yes           | `127.0.0.1`, `db`, `/cloudsql/...`            | Where MySQL lives. Use `db` for Docker Compose, `127.0.0.1` for a local install, `/cloudsql/…` for Cloud Run + Cloud SQL. |
| `DB_PORT`       | no            | `3306`                                        | MySQL port. Default `3306`.                                                                             |

**Special case:** if `DB_HOST` starts with `/`, [settings.py](settings.py) assumes
it's a Unix socket (how Cloud Run talks to Cloud SQL) and sets
`DATABASES['default']['OPTIONS'] = {'unix_socket': DB_HOST}` automatically.

Example `.env` for local development:
```env
DB_NAME=CulinaryGraph
DB_USER=root
DB_PASSWORD=your-mysql-root-password
DB_HOST=127.0.0.1
DB_PORT=3306
SECRET_KEY=dev-secret-key-change-me
DEBUG=1
ALLOWED_HOSTS=*
```

The real `.env` file is gitignored — don't commit it.

---

## 4. Run it

### Docker Compose

This uses [docker-compose.yml](docker-compose.yml) to start MySQL and the Django
app together. You don't need Python or MySQL installed — Docker Desktop is enough.

1. **Start Docker Desktop** and wait until it says "running".

2. Create `.env` as shown in section 3. Set `DB_HOST=db` (the Compose service name
   for MySQL).

3. Build and start both containers:
   ```bash
   docker compose up --build
   ```
   First run takes 3–5 minutes while Docker downloads base images and installs
   Python dependencies. Leave the terminal open — it streams logs.

4. When you see `Starting development server at http://0.0.0.0:8000/`, open
   [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

5. In a **second terminal**, apply migrations and seed the countries:
   ```bash
   docker compose exec web python manage.py migrate
   docker compose exec -T db mysql -uroot -p"$DB_PASSWORD" CulinaryGraph < schema.sql
   ```
   (The second command pipes [schema.sql](schema.sql) into MySQL running in the
   `db` container. On a database that already has tables from `migrate`, the
   `CREATE TABLE` statements will error — that's OK, the `INSERT INTO core_region`
   lines at the bottom of the file are what actually matter and will still run.)

6. To stop:
   ```bash
   docker compose down          # stops containers, keeps MySQL data
   docker compose down -v       # also deletes the MySQL volume (fresh start)
   ```

## 5. Verify it's working

After running the app with any option above:

1. Open the site in your browser. You should see the public landing page with the
   "Culinary Graph" hero.
2. Click **Join** and register with any email / password.
3. After registering, log in. You'll be redirected to the profile page. Pick a
   country, fill in the other fields, save.
4. From the dashboard, click **+ Add Recipe**. Typing `"franc"` into the **Countries**
   field should suggest "France" — that confirms the country list is seeded.
5. Publish a recipe and check that it appears on the dashboard under "My Latest
   Entries" and on `/recipes/`.

If any of these fail, see [Troubleshooting](#7-troubleshooting).

---

## 6. Deploy to Google Cloud Run (production)

### 6.1 Prerequisites

- A Google Cloud project with billing enabled
- A Cloud SQL MySQL 8 instance with an empty `CulinaryGraph` database
- `gcloud` CLI installed and authenticated: `gcloud auth login`
- The Cloud Run, Cloud Build, Artifact Registry, and Cloud SQL Admin APIs enabled
  on your project

Set the active project:
```bash
gcloud config set project YOUR_PROJECT_ID
```

### 6.2 One-time schema bootstrap

On a brand-new Cloud SQL instance, pipe [schema.sql](schema.sql) in. It contains
the full end-state schema, the country seed, and `django_migrations` rows so
Django's `migrate` will treat every migration as already applied:
```bash
gcloud sql connect YOUR_INSTANCE --user=root --database=CulinaryGraph < schema.sql
```

### 6.3 Deploy in one command

```bash
gcloud run deploy culinary-service \
  --source . \
  --region europe-west10 \
  --allow-unauthenticated \
  --add-cloudsql-instances PROJECT:REGION:INSTANCE \
  --set-env-vars DB_NAME=CulinaryGraph,DB_USER=root,DB_PASSWORD=YOUR_DB_PASSWORD,DB_HOST=/cloudsql/PROJECT:REGION:INSTANCE,SECRET_KEY=random-string,DEBUG=0,ALLOWED_HOSTS=*
```
What happens:
- `--source .` uploads the repo to Cloud Build, which packages the [Dockerfile](Dockerfile)
  and produces a container image in Artifact Registry.
- Cloud Run replaces the running revision with the new image.
- On container startup, the Dockerfile's `CMD` runs `python manage.py migrate --noinput`
  (idempotent) and then launches `gunicorn`.
- The command prints the service URL when it finishes — visit it to confirm.

