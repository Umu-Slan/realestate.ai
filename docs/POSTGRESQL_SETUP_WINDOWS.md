# PostgreSQL Setup for Windows

This project requires **PostgreSQL 14+** with the **pgvector** extension for local development and demo.

## 1. Install PostgreSQL

1. Download PostgreSQL for Windows: https://www.postgresql.org/download/windows/
2. Run the installer (e.g. **PostgreSQL 14** or newer).
3. During setup:
   - Set a **password for the `postgres` superuser** — remember it.
   - Default port: **5432** (keep unless you have conflicts).
4. Add PostgreSQL to `PATH` if not automatic (e.g. `C:\Program Files\PostgreSQL\14\bin`).

## 2. Start PostgreSQL Service

PostgreSQL runs as a Windows service.

- **Check status**: `Get-Service -Name postgresql*`
- **Start**: `net start postgresql-x64-14` (adjust version number if needed)
- Or: **Services** app → find **postgresql-x64-14** → Start

## 3. Create Database and User

Open PowerShell and run:

```powershell
# Connect as postgres (you'll be prompted for the postgres password)
psql -U postgres

# In psql:
CREATE DATABASE realestate_ai;
\connect realestate_ai
CREATE EXTENSION IF NOT EXISTS vector;
\q
```

Or as one-liners (you'll be prompted for password):

```powershell
psql -U postgres -c "CREATE DATABASE realestate_ai;"
psql -U postgres -d realestate_ai -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## 4. Configure `.env`

Copy the example and set your credentials:

```powershell
copy .env.example .env
```

Edit `.env` and set:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/realestate_ai
```

Replace `YOUR_PASSWORD` with the password you set for the `postgres` user.

Format: `postgresql://USER:PASSWORD@HOST:PORT/DATABASE`

## 5. Verify Setup

```powershell
python manage.py check_local_setup
```

This checks `.env`, `DATABASE_URL`, PostgreSQL connection, and pgvector.

## 6. If You Don't Know Your PostgreSQL Password

**→ See [POSTGRESQL_PASSWORD_RECOVERY_WINDOWS.md](POSTGRESQL_PASSWORD_RECOVERY_WINDOWS.md)** for a full step-by-step recovery guide.

**Fastest recovery paths:**
- **Option A (pgAdmin)**: Create a new user and database with a password you choose.
- **Option B (reset)**: Temporarily set `trust` in `pg_hba.conf`, connect without password, run `ALTER USER postgres PASSWORD 'new';`, then restore `md5`.

## pgvector Extension

The **pgvector** extension is required for the knowledge/RAG features.

- **Option A**: Install pgvector when installing PostgreSQL (see pgvector GitHub for Windows builds).
- **Option B**: The first knowledge migration (`knowledge.0001_initial`) runs `CREATE EXTENSION IF NOT EXISTS vector` automatically — but pgvector must be installed on the PostgreSQL server first.

If you get `extension "vector" is not available`:

1. Install pgvector for your PostgreSQL version: https://github.com/pgvector/pgvector#installation
2. Or use a PostgreSQL distribution that includes pgvector (e.g. some Docker images).
