---
name: substack-setup
description: Install dependencies and configure environment variables for the Substack skill project. Run this before using any other Substack skills.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
---

# Substack 项目环境配置 Skill

本 skill 指引 agent 完成项目依赖安装和环境变量配置，确保其他 skill（查询、爬虫）可以正常运行。

**本 skill 不涉及数据操作，仅做环境初始化。**

## When to use

Use this skill when:
- The project is freshly cloned and has not been set up yet
- The virtual environment `.venv/` does not exist
- The `.env` file does not exist
- The user explicitly asks to install or set up the project
- Other skills fail due to missing dependencies or missing `.env`

## Step 1: Create virtual environment

Check if `{baseDir}/.venv` exists. If not, create it:

```bash
python3 -m venv {baseDir}/.venv
```

## Step 2: Install Python dependencies

```bash
{baseDir}/.venv/bin/pip install -r {baseDir}/requirements.txt
```

Key dependencies (defined in `requirements.txt`):
- `requests` — HTTP client for the scraper
- `psycopg2-binary` — PostgreSQL driver
- `python-dotenv` — Load `.env` config
- `financial-hub-postgres` — Shared database client library

## Step 3: Configure environment variables

Check if `{baseDir}/.env` exists. If not, copy from the example file:

```bash
cp {baseDir}/.env.example {baseDir}/.env
```

Then ask the user to fill in the actual values. The variables are:

| Variable | Description | Example |
|---|---|---|
| `POSTGRES_HOST` | PostgreSQL server address | `127.0.0.1` |
| `POSTGRES_PORT` | PostgreSQL server port | `5432` |
| `POSTGRES_USER` | Database user (for crawler, read-write) | `hub_user` |
| `POSTGRES_PASSWORD` | Password for the read-write user | `hub_password` |
| `POSTGRES_DB` | Database name | `financial_hub` |
| `POSTGRES_READONLY_USER` | Database user (for query skill, read-only) | `hub_readonly` |
| `POSTGRES_READONLY_PASSWORD` | Password for the read-only user | `hub_password` |

**Important:** The `.env` file contains sensitive credentials and is already in `.gitignore`. Never commit it to version control.

## Step 4: Verify setup

Run the query tool to verify the database connection is working:

```bash
{baseDir}/.venv/bin/python {baseDir}/query_db.py stats
```

If this command prints statistics without errors, the setup is complete.

If it fails with a connection error, ask the user to check:
1. Is PostgreSQL running and accessible at the configured host/port?
2. Are the database credentials correct?
3. Does the database and the readonly user exist?

## Step 5: Create readonly database user (if needed)

If Step 4 fails because the `hub_readonly` user does not exist, create it by running:

```bash
{baseDir}/.venv/bin/python -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv('{baseDir}/.env')
conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
    port=int(os.getenv('POSTGRES_PORT', '5432')),
    user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD'),
    dbname=os.getenv('POSTGRES_DB'),
)
conn.autocommit = True
cur = conn.cursor()
ro_user = os.getenv('POSTGRES_READONLY_USER', 'hub_readonly')
ro_pass = os.getenv('POSTGRES_READONLY_PASSWORD', 'hub_password')
cur.execute(f\"CREATE ROLE {ro_user} WITH LOGIN PASSWORD '{ro_pass}'\")
cur.execute(f'GRANT CONNECT ON DATABASE {os.getenv(\"POSTGRES_DB\")} TO {ro_user}')
cur.execute(f'GRANT USAGE ON SCHEMA public TO {ro_user}')
cur.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO {ro_user}')
cur.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {ro_user}')
cur.close()
conn.close()
print(f'Created readonly user: {ro_user}')
"
```

Then re-run Step 4 to verify.

## Examples

User says: "帮我安装substack技能的依赖"
→ Execute Step 1 and Step 2.

User says: "配置substack项目的环境变量"
→ Execute Step 3, then ask the user for actual database credentials.

User says: "初始化substack项目"
→ Execute Step 1 through Step 4.

User says: "substack查询工具连不上数据库"
→ Check `.env` is present and correct (Step 3), then run Step 4 to diagnose. If readonly user missing, run Step 5.

## Project structure reference

```
{baseDir}/
├── .env.example        ← Environment variable template
├── .env                ← Actual config (not in git)
├── .venv/              ← Python virtual environment (not in git)
├── requirements.txt    ← Python dependencies
├── schema.sql          ← Database table definitions
├── scraper.py          ← Substack HTTP scraper functions
├── main.py             ← Crawler main entry point (read-write)
├── query_db.py         ← Database query tool (read-only)
├── SKILL.md            ← Query skill definition
├── SKILL_SETUP.md      ← This file (setup skill)
└── README.md           ← User-facing documentation
```
