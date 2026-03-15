# PostgreSQL Password Recovery on Windows

If you get **"password authentication failed for user postgres"** and you do **not** know the PostgreSQL password, use this guide to recover local setup.

---

## Fastest Recovery Path

| Option | When to use | Effort |
|--------|-------------|--------|
| **A: pgAdmin** | pgAdmin is installed and you can log in | Quick — create new user with known password |
| **B: Reset postgres password** | No pgAdmin, or you prefer fixing `postgres` | ~5 min — temporary config change |

Both options end with: update `.env` → run `python manage.py check_local_setup` → continue setup.

---

## Step 0: Check PostgreSQL Is Running

```powershell
# List PostgreSQL services
Get-Service -Name postgresql*

# If stopped, start (adjust version if needed):
net start postgresql-x64-14
```

If no service exists, PostgreSQL is not installed. See [POSTGRESQL_SETUP_WINDOWS.md](POSTGRESQL_SETUP_WINDOWS.md).

---

## Step 1: Find Your PostgreSQL Version and Service Name

```powershell
Get-Service -Name postgresql*
```

Typical names: `postgresql-x64-14`, `postgresql-x64-15`, `postgresql-x64-16`.

Data directory is usually: `C:\Program Files\PostgreSQL\<VERSION>\data\`

---

## Option A: Use pgAdmin (Create New User + DB)

If pgAdmin was installed with PostgreSQL and you can open it:

1. **Open pgAdmin** (from Start menu or `C:\Program Files\PostgreSQL\<VERSION>\pgAdmin 4\`).
2. **Connect** — if prompted for the postgres password and you don’t know it, use Option B instead.
3. If you **can** connect:
   - Right‑click **Login/Group Roles** → **Create** → **Login/Group Role**
   - **General**: Name = `realestate_dev`
   - **Definition**: Password = `demo123` (or any password you choose)
   - **Privileges**: Enable **Can login**
   - Save
4. Right‑click **Databases** → **Create** → **Database**
   - Name: `realestate_ai`
   - Owner: `realestate_dev`
   - Save
5. Right‑click database `realestate_ai` → **Query Tool**, run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
6. Update `.env`:
   ```env
   DATABASE_URL=postgresql://realestate_dev:demo123@localhost:5432/realestate_ai
   ```
7. Verify:
   ```powershell
   python manage.py check_local_setup
   ```

---

## Option B: Reset postgres Password (No Password Needed)

This uses a temporary `trust` setting so you can connect without a password and set a new one.

### 1. Run PowerShell as Administrator

Right‑click PowerShell → **Run as administrator**.

### 2. Find pg_hba.conf

Common path: `C:\Program Files\PostgreSQL\14\data\pg_hba.conf`  
Adjust `14` for your version.

### 3. Edit pg_hba.conf

Open in Notepad (as Administrator if needed):

```powershell
notepad "C:\Program Files\PostgreSQL\14\data\pg_hba.conf"
```

Find lines like:

```
# IPv4 local connections:
host    all             all             127.0.0.1/32            md5
# IPv6 local connections:
host    all             all             ::1/128                 md5
```

Change `md5` to `trust` **only** for these two lines:

```
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
```

Save and close.

### 4. Restart PostgreSQL

```powershell
net stop postgresql-x64-14
net start postgresql-x64-14
```

### 5. Connect and Set New Password

```powershell
psql -U postgres -h 127.0.0.1
```

In psql:

```sql
ALTER USER postgres PASSWORD 'YourNewPassword123';
\q
```

Replace `YourNewPassword123` with a password you will remember.

### 6. Restore pg_hba.conf (Security)

Open `pg_hba.conf` again and change `trust` back to `md5` for both lines. Save.

### 7. Restart PostgreSQL Again

```powershell
net stop postgresql-x64-14
net start postgresql-x64-14
```

### 8. Create Database and pgvector

```powershell
psql -U postgres -h 127.0.0.1 -c "CREATE DATABASE realestate_ai;"
psql -U postgres -h 127.0.0.1 -d realestate_ai -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Enter your new password when prompted.

### 9. Update .env

```env
DATABASE_URL=postgresql://postgres:YourNewPassword123@localhost:5432/realestate_ai
```

### 10. Verify

```powershell
cd <your-project-directory>
.venv\Scripts\activate
python manage.py check_local_setup
```

---

## After Recovery: Finish Setup

```powershell
python manage.py migrate
python manage.py run_demo
```

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| `psql` not found | Add `C:\Program Files\PostgreSQL\<VERSION>\bin` to PATH, or use full path |
| Access denied editing pg_hba.conf | Run Notepad as Administrator |
| Service won't start | Check Event Viewer → Windows Logs → Application |
| pgvector not available | Install pgvector for your PostgreSQL version; see [POSTGRESQL_SETUP_WINDOWS.md](POSTGRESQL_SETUP_WINDOWS.md#pgvector-extension) |
