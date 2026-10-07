# query-inspector - tuning-report Manual

**English** | [한국어](./MANUAL-tuning-report.ko.md)

The manual for **`tuning-report`**, one of query-inspector's two skills. Run it and it **extracts the SQL/ORM queries in your git changes and tunes them (missing indexes / N+1 / anti-patterns, etc.)** into a report. To list the project's queries instead of tuning, use the sibling skill **[`inventory-report`](./MANUAL-inventory-report.md)**.

> Both skills at a glance: [MANUAL.md](./MANUAL.md) / intro: [README.md](./README.md) / full install guide: [INSTALL.md](./INSTALL.md) / design: [DESIGN.md](./DESIGN.md) / quick reference while running: `--help` (= `assets/help.md`).

---

## 1. Overview

`tuning-report` is invoked manually. Its default flow is **incremental - only the changes since your last tuning** (a full run is also possible). **Running it right before you commit is the most useful** - it catches performance problems before they reach the repository. It never edits your code; it produces a report with suggestions. The runtime scripts are all Python, so it works the same on **mac / Linux / Windows**.

### Key features
- **Primary targets**:
  - missing indexes (with ready-to-use `CREATE INDEX` suggestions)
  - N+1 queries
  - common anti-patterns (index-defeating predicates / leading-wildcard `LIKE '%..'` / dialect-mismatched syntax / needless `SELECT *`, etc.)
- **Incremental + follow-up**: checks whether previous suggestions were actually applied - including files you didn't touch this run.
- **Auto-degrading tiers (3-Tier)**: static heuristics -> schema index matching -> (optional) live-DB EXPLAIN.
- **Broad stacks**:
  - `Kotlin / Java` + MyBatis / native SQL / JPA/Hibernate (derived methods / `@Query` / QueryDSL / Kotlin JDSL)
  - **Python (Django / SQLAlchemy)**: supported, though not as thoroughly validated as the primary stacks
  - dialects (MySQL / MariaDB, etc.) auto-detected
- **Ready-to-use report**: severity-ranked summary + Action Items (file / line / paste-ready code / DDL)
- **Guardrails**: live-DB access is opt-in, production is blocked, read-only queries only

---

## 2. Install

query-inspector installs as a plugin (there is no skill-copy install - the two skills share assets under one namespace). Use `--local` to install from your own checkout instead of the public marketplace.

```bash
bash query-inspector-setup.sh              # user-global (default) -> /query-inspector:tuning-report
bash query-inspector-setup.sh --project    # project-local (this project only)
bash query-inspector-setup.sh --local      # install from THIS checkout (clone/fork/offline)
```
On **Windows**, run `query-inspector-setup.bat` with the same options.<br>
`--project` runs from the target project root (elsewhere, pass `--project <path>`).

**Requirements:**
- `git`
- `python3` (mac/linux) or `python`/`py` (Windows) - standard library only
- Tier 3 (live-DB EXPLAIN, optional):
  - MySQL: the `mysql` CLI or `pymysql`
  - PostgreSQL: `psql` or `psycopg`
  - `PyYAML`
- A private repo needs git auth; a public repo needs none.

> The skill **never installs anything for you**. If `git`/`python` is missing the skill won't run, so install it yourself; if a Tier 3 driver (`pymysql`/`psycopg`) is missing it falls back to the `mysql`/`psql` CLI, and if the CLI is also missing it **auto-degrades to Tier 2** (noted in the report). `PyYAML` is only needed to parse Tier 3 profiles; if it's missing the skill points you to install it.

**Update:** `claude plugin update query-inspector@query-inspector-marketplace` -> restart claude (the `/plugin` slash command only opens the management UI; it does not update).<br>
**Uninstall:** `claude plugin uninstall query-inspector@query-inspector-marketplace`<br>
Auto-update: [section 8](#8-auto-update)

> **Full install guide -> [INSTALL.md](./INSTALL.md)** - plugin vs. skill, manual install, project-local, getting the setup script, verification.

---

## 3. Quick start

In a new Claude Code session (invoked by namespace, regardless of install method):
```
/query-inspector:tuning-report            # changes since last tuning (asks for scope on first run)
```
On its first run `tuning-report` reports the scope size and lets you choose (full/progressive / recent commits / a specific path).

Results:
- a terminal summary
- a detail report: `docs/query-inspector/tuning-reports/<timestamp>.md`

```bash
# Typical pre-commit flow
cp .query-inspector.example.yml .query-inspector.yml   # optional - works with defaults
git add .
claude
> /query-inspector:tuning-report
```

---

## 4. Command / option reference

| Option | Description |
|--------|-------------|
| (none) | changes since last tuning (incremental); asks for scope on first run |
| `--all` | ignore prior runs/baseline; scan **all** query sources |
| `--staged` | staged changes only |
| `--range <rev>` | a given range (e.g. `main..HEAD`, `HEAD~3`) |
| `--files <paths...>` | specific files only |
| `--continue` | resume an in-progress progressive full scan at the next domain |
| `--depth static\|schema\|explain` | force a tier (1/2/3) |
| `--db <profile>` | deepen with live-DB EXPLAIN (opt-in) |
| `--dialect mysql\|mariadb\|postgresql\|oracle\|ansi` | force the dialect (default: auto-detect) |
| `--lang ko\|en\|ja\|zh` | output language (default `report.language=auto`) |
| `--no-state` | run once without reading/writing state |
| `--reset-state` | reset state (next run is full) |
| `--no-update-check` | skip the new-version check this run |
| `--version` | print the installed version (e.g. `query-inspector v1.0.0 (plugin)`) |
| `--help`, `-h` | help |

**Option groups**

- **Target scope** (`--all` / `--staged` / `--range` / `--files` / `--continue`):
  - Decides what gets scanned. With no flag, it is **incremental** (changes since the last tuning).
  - An explicit scope (`--all` / `--range` / `--files` / `--staged`) ignores the incremental baseline and looks only at that scope.
  - `--continue` resumes an in-progress progressive full scan at the next domain.
- **Tuning depth / DB** (`--depth` / `--db` / `--dialect`):
  - `--depth` forces a tier (`static`=Tier 1, `schema`=Tier 2, `explain`=Tier 3). Without it, the highest feasible tier is chosen and degraded when prerequisites are missing.
  - `--db <profile>` turns on live-DB EXPLAIN (Tier 3). `<profile>` is a name defined under `db.profiles` in `.query-inspector.yml` (setup and behavior in [section 7](#7-tier-3---live-db-explain-optional)).
  - `--dialect` sets the dialect explicitly instead of auto-detecting it.
- **State (incremental)** (`--no-state` / `--reset-state`):
  - `--no-state` runs once without reading or writing the state file.
  - `--reset-state` clears the state (the next run is full).
- **Output / misc** (`--lang` / `--no-update-check` / `--version` / `--help`):
  - `--lang` forces the output language (default `report.language=auto`).
  - `--no-update-check` skips the new-version check for this run.
  - `--version` / `--help` print the version / help and exit.

**Common combinations**
- Always full, regardless of prior runs: `--all` (add `--no-state` to leave state untouched).
- Branch review: `--range main..HEAD`.
- Deepen a specific run with a real plan: `--db <profile>` (see [section 7](#7-tier-3---live-db-explain-optional)).

---

## 5. How it works

`tuning-report` collects the changes in your project, extracts queries, reconstructs SQL, then analyzes them across three tiers to build the report.

- **Incremental (default)**: changes since the last-tuned commit in the state file (`docs/query-inspector/tuning-reports/state.json`), plus uncommitted and new files. The **first run** asks for scope rather than scanning everything.
- **Progressive full scan**: when a full scan is heavy, it goes domain by domain (top-level package/directory), one batch at a time, resumable with `--continue`.
- **3-Tier auto-degrade**:
  - (1) Tier 1 static heuristics (always) -> (2) Tier 2 schema index matching (auto-detected entities / migrations / DDL, or `--db`) -> (3) Tier 3 live-DB EXPLAIN (`--db`).
  - It raises the tier as far as the inputs allow and degrades otherwise, noting it in the report.
- **Dialect auto-detection**:
  - build dependencies -> datasource URL -> Hibernate config -> migration traits.
  - Falls back to MySQL if undetermined.
  - Override with `--dialect`.
- **Follow-up**:
  - compares prior `open_suggestions` against the current code/schema and marks status (✅ resolved / ⚠️ not applied / ❓ needs check).
  - Skipped on the first run and with `--all`.

---

## 6. Reading the report

Results come as a report; your code is never edited.

- **Terminal summary**: top N by severity (`terminal_top_n`, default 10). Each row shows severity / issue / location / last modifier / confidence.
- **Detail report file**:
  - generated at `docs/query-inspector/tuning-reports/<timestamp>.md`.
  - Full example: [examples/sample-report.md](./examples/sample-report.md)
- **Action Items**:
  - organized so a developer, or that developer's AI, can start right away.
  - Labels: `[auto-apply]` (mechanically safe) / `[review]` (needs a design call) / `[confirm]` (verify a premise first)
  - paste-ready DDL is provided for things like adding indexes.
- **Last modifier**: who last wrote/changed the source `file:line` (git blame); "uncommitted (in progress)" when not yet committed.
- **Confidence labels**:
  - `EXACT` (verbatim) / `INFERRED` (ORM translation) / `AMBIGUOUS` (a representative case of a dynamic query)
  - for ORM/dynamic queries, verify the real SQL (e.g. `show_sql`).

### Report example (incremental, 2nd run)

```markdown
# Query Tuning Report - incremental (2 changed files)
- Severity (open): 🔴 3 / 🟡 2 / ⚪ 1   /   Follow-up: ✅ 2 resolved / ⚠️ 2 still open (2nd time)

## 🔴 [critical] Missing index - FK `orders.user_id` - OrderMapper.xml (SCHEMA-CONFIRMED / 2nd time)
- Why critical: it is the N+1 child query, so every user triggers a full scan of `orders`.
- Suggestion:  CREATE INDEX idx_orders_user_id ON orders (user_id);
- Verify (Tier 3, --db): EXPLAIN shows `type: ALL -> ref`.

## ✅ Action Items
- [ ] [auto-apply] Add index migration - new file V3__orders_indexes.sql (2nd reminder)
      CREATE INDEX idx_orders_user_id        ON orders (user_id);
      CREATE INDEX idx_orders_status_created ON orders (status, created_at);
```

ORM dynamic queries can't be reconstructed 100%, so every inferred query carries a confidence label and `AMBIGUOUS` items come with how to verify the real SQL.

---

## 7. Tier 3 - live-DB EXPLAIN (optional)

Use this when you want to confirm index suggestions against a real plan.<br>
**No production / read-only / opt-in** are enforced.

```bash
/query-inspector:tuning-report --db dev
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
      allow_explain_analyze: false       # whether EXPLAIN ANALYZE (real execution) is allowed
      host_allowlist: [localhost, 127.0.0.1, dev-db.internal]  # hosts outside this list are blocked (add your dev DB, e.g. a private IP)
      host_denylist_patterns: ["*prod*", "*live*", "*production*"]  # blocked name patterns
      statement_timeout_ms: 3000         # statement timeout
      max_rows: 100000                   # expected-scan row cap (warns above it)
```

- `url_env` / `env_file`: the connection URL is read only from an env var or `.env` (never stored in config); see the sourcing order below.
- `host_allowlist`: when non-empty, every host outside the list is blocked - **add your dev DB (private IP, etc.)**.
- `allow_explain_analyze`: only when `true` is `--analyze` (EXPLAIN ANALYZE) allowed, and even then it runs inside a transaction that is always rolled back.
- `statement_timeout_ms` / `max_rows`: statement timeout and expected-scan row cap (guardrails).

### Credential sourcing (in order)
1. the profile's `url_env` env var (the skill also auto-loads `.env`)
2. **auto-extract from the project datasource config**:
   - `spring.datasource.*` (or `r2dbc.*`) in `application.yml`/`.properties` (and `application-{local,dev}.*`); production configs (`application-prod*`) are excluded.
   - It **confirms "connect to host:port/db?" before connecting**.
3. Otherwise, the skill **asks you to prepare it and run again** (for security, **it never takes the password directly in the chat**). Prepare it in one of these ways:
   - **Save to `.env` (recommended)**: **in a terminal**, `python3 scripts/set_db_credential.py --var QT_DEV_DB_URL` (Windows `python`/`py`). It reads the URL via **hidden input** and saves it to `.env` (hidden input needs a real terminal, so it is refused under claude's non-interactive execution).
   - **Shell `export`**: `export QT_DEV_DB_URL="postgresql://..."` (a shell env var takes precedence over `.env`).

- **Special characters in the password**: URL-reserved characters like `#`/`@`/`!` need percent-encoding (`#`->`%23`).
- Saving via `set_db_credential.py` encodes them automatically, so you can type the password as-is.

### Guardrails
- Production hosts (name patterns / public IPs) and anything other than `SELECT`/`EXPLAIN` are blocked (read-only).
- A profile with a `host_allowlist` blocks hosts outside it, so **add your dev DB (private IP, etc.) to the profile's `host_allowlist`**.
- `EXPLAIN ANALYZE` (real execution) runs only with the profile's `allow_explain_analyze: true` plus confirmation, inside a transaction that is always rolled back.
- Connection URLs and passwords are never written to the report or logs.
- If neither the driver nor the CLI is present, it auto-degrades to Tier 2 (noted in the report).

Live sandboxes to try it: [`examples/docker-mysql/`](./examples/docker-mysql/), [`examples/docker-postgres/`](./examples/docker-postgres/).

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
Key settings: `stacks` (adapters), `dialect` (default `auto`), `schema` (Tier 2 sources), `depth`, `report` (`dir`/`language`/`min_severity`/`terminal_top_n`/`update_check`), `severity_rules` (per-heuristic severity), `state` (incremental), `db` (Tier 3 profiles).

`report.dir` is the report root (default `docs/query-inspector`); tuning reports and `state.json` go under its `tuning-reports/` subdirectory.

> 🔒 These files sit in **the repo of the project being tuned**.<br>
> When you use `--db`, the connection URL goes through an env var / `.env` only (the config file holds just the variable name), and the skill auto-adds `.env` to that project's `.gitignore`.<br>
> Keeping it out of version control is recommended, and it's best not to put a real URL in `.query-inspector.yml` either.

---

## 10. FAQ / troubleshooting

| Symptom | Fix |
|---------|-----|
| Want to know the installed version | `/query-inspector:tuning-report --version` (or `claude plugin list`, or the cache path `~/.claude/plugins/cache/query-inspector-marketplace/query-inspector/<version>/`). The report header also shows it. |
| Command not visible | Ensure it's a new session; for the plugin check `/plugin list` for `query-inspector`, for the skill check `~/.claude/skills/query-inspector/` (Windows `%USERPROFILE%\.claude\skills\query-inspector\`). |
| `python3` not found (often Windows) | Use `python` or `py` (`py --version`). Only `git` and `python` are needed - no bash. |
| "Not a git repository" | Run inside a git repo (`git init`). |
| Missing `pymysql`/`PyYAML` for Tier 3 | Falls back to the `mysql` CLI or degrades to Tier 2. Install if needed: `pip install pymysql pyyaml`. |
| Tier 3 connection URL fails to parse | Percent-encode reserved chars (`#`,`@`,`!`) in the password, or save via `set_db_credential.py` (auto-encodes). |
| Blocked / outside allowlist | If the target is a dev DB, add its host to the profile's `host_allowlist`. |
| Only part was reviewed | Incremental mode (expected). Use `--all` for everything. |
| Report not visible | Check `docs/query-inspector/tuning-reports/<timestamp>.md` (path per `report.dir`). |

---

For design background see [DESIGN.md](./DESIGN.md); for the change history see [CHANGELOG.md](./CHANGELOG.md).
