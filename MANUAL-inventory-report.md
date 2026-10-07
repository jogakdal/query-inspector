# query-inspector - inventory-report Manual

**English** | [한국어](./MANUAL-inventory-report.ko.md)

The manual for **`inventory-report`**, one of query-inspector's two skills. It **extracts the project's queries (ORM-generated ones included) and lists them as a catalog** - purpose, target tables, full query body, index coverage. This is cataloging, **not** tuning; for anti-pattern analysis and fix suggestions, use the sibling skill **[`tuning-report`](./MANUAL-tuning-report.md)**.

> Both skills at a glance: [MANUAL.md](./MANUAL.md) / intro: [README.md](./README.md) / full install guide: [INSTALL.md](./INSTALL.md) / design: [DESIGN.md](./DESIGN.md) / quick reference while running: `--help` (= `assets/help.md`).

---

## 1. Overview

`inventory-report` builds a **catalog of the queries a project runs** - both explicit SQL and the SQL that ORM / dynamic queries generate. It supports a broad range of stacks: Kotlin/Java + MyBatis / native SQL / JPA/Hibernate (derived methods, `@Query`, QueryDSL, Kotlin JDSL). **Python (Django / SQLAlchemy) is supported too, though not as thoroughly validated as the primary stacks.** Dialects are auto-detected. Its main output is the **full body of every query**, alongside where each comes from and whether an index covers it. As cataloging, it assigns no severity and suggests no fixes. The runtime scripts are all Python, so it works the same on **mac / Linux / Windows**.

### Report contents
- **Full query body (primary output)**: the inferred SQL body of every query, in full; dynamic queries get 2-3 representative scenarios, each in full.
- **Per-query detail**: purpose/use, target table (+ schema), type (`SELECT`/`INSERT`/`UPDATE`/`DELETE`/`DDL`), source (`file:line` + adapter + confidence label), **last modifier** (git blame), access columns, index coverage.
- **Index coverage**: whether the access path (`WHERE` / `JOIN` / `ORDER BY` columns) is covered by an index (`✅ <index>` / `❌ uncovered` / `❓ schema unknown`).

---

## 2. Install

query-inspector installs as a plugin (there is no skill-copy install - the two skills share assets under one namespace). Use `--local` to install from your own checkout instead of the public marketplace.

```bash
bash query-inspector-setup.sh              # user-global (default) -> /query-inspector:inventory-report
bash query-inspector-setup.sh --project    # project-local (this project only)
bash query-inspector-setup.sh --local      # install from THIS checkout (clone/fork/offline)
```
On **Windows**, run `query-inspector-setup.bat` with the same options.<br>
`--project` runs from the target project root (elsewhere, pass `--project <path>`).

**Requirements:**
- `git`
- `python3` (mac/linux) or `python`/`py` (Windows) - standard library only
- To confirm index coverage against a live DB:
  - MySQL: the `mysql` CLI or `pymysql`
  - PostgreSQL: `psql` or `psycopg`
  - `PyYAML`
- A private repo needs git auth; a public repo needs none.

> The skill **never installs anything for you**. If `git`/`python` is missing the skill won't run, so install it yourself; if the live-DB driver (`pymysql`/`psycopg`) is missing it falls back to the `mysql`/`psql` CLI, and if the CLI is also missing it uses only the code's schema info or leaves index coverage as `❓ schema unknown`. `PyYAML` is only needed to parse `--db` profiles; if it's missing the skill points you to install it.

**Update:** `claude plugin update query-inspector@query-inspector-marketplace` -> restart claude (the `/plugin` slash command only opens the management UI; it does not update).<br>
**Uninstall:** `claude plugin uninstall query-inspector@query-inspector-marketplace`<br>
Auto-update: [section 8](#8-auto-update)

> **Full install guide -> [INSTALL.md](./INSTALL.md)** - plugin vs. skill, manual install, project-local, getting the setup script, verification.

---

## 3. Quick start

In a new Claude Code session (invoked by namespace, regardless of install method):
```
/query-inspector:inventory-report                     # whole project (default)
/query-inspector:inventory-report --range main..HEAD  # only the queries this branch changed
/query-inspector:inventory-report --staged            # only staged changes
```
The default is the whole project. To catalog **only a change set** (a PR or branch), scope it with `--range` / `--staged` / `--files`; the output format is the same, just narrower.

Results:
- a terminal summary (query counts by type/table + a top list)
- a detail report holding **every query's full body**: `docs/query-inspector/inventory-reports/inventory-<timestamp>.md`

---

## 4. Command / option reference

| Option | Description |
|--------|-------------|
| (none) | catalog **all** the project's queries (full) |
| `--all` | same as the default (explicit full) |
| `--range <rev>` | queries in a given range only (e.g. `main..HEAD`) |
| `--files <paths...>` | specific files only |
| `--staged` | staged changes only |
| `--continue` | resume an in-progress progressive full scan at the next domain |
| `--db <profile>` | confirm index coverage against the live-DB schema (opt-in) |
| `--dialect mysql\|mariadb\|postgresql\|oracle\|ansi` | force the dialect (default: auto-detect) |
| `--lang ko\|en\|ja\|zh` | output language (default `report.language=auto`) |
| `--no-update-check` | skip the new-version check this run |
| `--version` | print the installed version (e.g. `query-inspector v1.0.0 (plugin)`) |
| `--help`, `-h` | help |

**Option groups**

- **Target scope** (`--all` / `--staged` / `--range` / `--files` / `--continue`):
  - Decides what gets cataloged. With no flag, the **whole project**.
  - `--range` / `--files` / `--staged` catalog only the changed queries in that scope.
  - `--continue` resumes an in-progress progressive full scan at the next domain.
- **DB / dialect** (`--db` / `--dialect`):
  - `--db <profile>` confirms index coverage against the live-DB schema (opt-in). `<profile>` is a name defined under `db.profiles` in `.query-inspector.yml` (setup in [section 7](#7-live-db-schema-for-index-coverage-optional)).
  - `--dialect` sets the dialect explicitly instead of auto-detecting it.
- **Output / misc** (`--lang` / `--no-update-check` / `--version` / `--help`):
  - `--lang` forces the output language (default `report.language=auto`).
  - `--no-update-check` skips the new-version check for this run.
  - `--version` / `--help` print the version / help and exit.

---

## 5. How it works

`inventory-report` collects the project's changes, extracts queries, and reconstructs SQL, then adds an access path and index coverage to each query to build the catalog.

- **Whole project by default:**
  - The target is "every query in the project".
  - Large repos are cataloged **by domain (a top-level package/directory - e.g. `order` / `user` / `payment`), one domain at a time**, continuing to the next with `--continue`.
  - With `--range` / `--files` / `--staged`, only that range is cataloged.
- **Index coverage:**
  - Checks whether an index covers the columns each query uses (`WHERE` / `JOIN` / `ORDER BY`).
  - Index info comes from the code's schema / entities / migrations (auto-detected), or from the live-DB schema with `--db`.
  - With no schema, only the index field stays `❓ schema unknown`; purpose / table / body are still filled in.
- **No judging:** it only lists; it assigns no severity and suggests no fixes.
- **Dialect auto-detection:**
  - build dependencies -> datasource URL -> Hibernate config -> migration traits.
  - Falls back to MySQL if undetermined.
  - Override with `--dialect`.

---

## 6. Reading the inventory

- **Terminal summary**: query counts by type/table + a top list; the header shows the skill version.
- **Detail file**: `docs/query-inspector/inventory-reports/inventory-<timestamp>.md`, holding every query's full body.

Each query lists:
- **Purpose / use**: a one-line description inferred from the method name / mapper id / surrounding code (marked when uncertain).
- **Target**: table(s) (+ schema / DB when known).
- **Type**: `SELECT` / `INSERT` / `UPDATE` / `DELETE` / `DDL`.
- **Source**: `file:line` (+ method / mapper id), adapter, confidence label (`EXACT` / `INFERRED` / `AMBIGUOUS`).
- **Last modifier**: who last wrote/changed the source `file:line` (git blame); "uncommitted (in progress)" when not yet committed.
- **Access columns**: `WHERE` / `JOIN` / `ORDER BY` columns.
- **Index coverage**: `✅ <index>` / `❌ uncovered` / `❓ schema unknown`.
- **Query body (full)**: the inferred SQL body in full; dynamic queries get 2-3 representative scenarios, each in full (labeled `AMBIGUOUS`).

> ⚠️ **The full query body is the main output**, so never abbreviate, summarize, `...`-truncate, or list "just a few representative ones" because there are many queries.<br>
> When you expect many queries, use **domain batches / a narrower scope + `--continue`**.

---

## 7. Live-DB schema for index coverage (optional)

Index coverage is confirmed from schema files or entities/migrations by default. To confirm it against a **real database schema** instead, use `--db`:

```bash
/query-inspector:inventory-report --db dev
```

### Profile setup (`.query-inspector.yml`)

Define the profile that `--db <name>` refers to under `db.profiles`:

```yaml
db:
  env_file: .env            # file holding credentials (gitignored); a shell env var takes precedence
  prod_guard: true          # block production hosts / name patterns outright (on by default)
  profiles:
    dev:                                 # -> use with `--db dev`
      url_env: QT_DEV_DB_URL             # env var name to read the URL from (example - use any name); the URL value itself never goes in config
      readonly: true                     # use a read-only account
      host_allowlist: [localhost, 127.0.0.1, dev-db.internal]  # hosts outside this list are blocked (add your dev DB, e.g. a private IP)
      host_denylist_patterns: ["*prod*", "*live*", "*production*"]  # blocked name patterns
      statement_timeout_ms: 3000         # statement timeout
```

- `--db` only **reads the schema** to confirm index coverage (it runs no EXPLAIN).
- `host_allowlist`: when non-empty, every host outside the list is blocked - **add your dev DB (private IP, etc.)**.

### Guardrails
**No production / read-only / opt-in**
- Production hosts (name patterns / public IPs) and anything other than `SELECT`/`EXPLAIN` are blocked.
- Add your dev DB host to the profile's `host_allowlist`.
- The connection URL is read at run time from the profile's `url_env` (a shell env var or `.env`). If it's missing, it is auto-extracted from the project datasource config (production excluded, with a confirm-before-connect prompt); failing that, the skill **asks you to prepare it and run again** (for security, **it never takes the password directly in the chat**).
- Prepare the URL in advance, in one of these ways:
  - **Save to `.env` (recommended)**: **in a terminal**, `python3 scripts/set_db_credential.py --var QT_DEV_DB_URL` (Windows `python`/`py`). It reads the URL via **hidden input** and saves it to `.env`; `--var` takes the same name as the profile's `url_env`, and reserved characters (`#`/`@`/`!`) are percent-encoded automatically. (Hidden input needs a real terminal, so it is refused under claude's non-interactive execution.)
  - **Shell `export`**: `export QT_DEV_DB_URL="postgresql://..."` (a shell env var takes precedence over `.env`).
- The connection URL / password are never written to the report or logs (the AI does not read them; an internal DB-connection script does).

---

## 8. Auto-update

The skill quietly checks **once a day** at runtime for a new version (it silently skips on a network/auth/git failure).
- It points you to run `claude plugin update query-inspector@query-inspector-marketplace` (restart claude to apply).
- Or turn on auto-update under `/plugin` -> Marketplaces to refresh automatically after session start.
- For a `--local` install, `git pull` in your checkout, then `claude plugin marketplace update ...` and `claude plugin update ...`.
- Turn it off with `--no-update-check` or `report.update_check: false`.

---

## 9. Configuration (`.query-inspector.yml`)

Works with defaults; copy the template to adjust.
```bash
cp .query-inspector.example.yml .query-inspector.yml
```
Settings relevant to inventory: `stacks` (adapters), `dialect` (default `auto`), `schema` (index-coverage sources), `report` (`dir`/`language`/`terminal_top_n`/`update_check`), `db` (live-schema profiles).

`report.dir` is the report root (default `docs/query-inspector`); inventory reports go under its `inventory-reports/` subdirectory.

> 🔒 These files sit in **the repo of the project being cataloged**.<br>
> When you use `--db`, the connection URL goes through an env var / `.env` only (the config file holds just the variable name), and the skill auto-adds `.env` to that project's `.gitignore`.<br>
> Keeping it out of version control is recommended, and it's best not to put a real URL in `.query-inspector.yml` either.

---

## 10. FAQ / troubleshooting

| Symptom | Fix |
|---------|-----|
| Want to know the installed version | `/query-inspector:inventory-report --version` (or `claude plugin list`). The inventory header also shows it. |
| Command not visible | Ensure it's a new session; for the plugin check `/plugin list` for `query-inspector`, for the skill check `~/.claude/skills/query-inspector/` (Windows `%USERPROFILE%\.claude\skills\query-inspector\`). |
| `python3` not found (often Windows) | Use `python` or `py` (`py --version`). Only `git` and `python` are needed - no bash. |
| "Not a git repository" | Run inside a git repo (`git init`). |
| The body looks truncated / only some queries listed | By design the detail file holds every query's full body. If a run feels partial, it's the batch boundary - continue with `--continue` (large repos are cataloged domain by domain). |
| Index coverage shows `❓ schema unknown` | No schema was found. Add schema files/entities/migrations, or pass `--db <profile>` to confirm against the live schema. |
| Inventory not visible | Check `docs/query-inspector/inventory-reports/inventory-<timestamp>.md` (path per `report.dir`). |

---

For design background see [DESIGN.md](./DESIGN.md); for the change history see [CHANGELOG.md](./CHANGELOG.md).
