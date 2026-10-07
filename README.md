# query-inspector

**English** | [한국어](./README.ko.md)

> query-inspector is a **Claude Code skill for SQL and ORM query tuning**, packaged as a plugin with **two skills**.<br>
> **`tuning-report`** performs **query tuning** on the queries in your changes (N+1s, missing indexes, anti-patterns), and **`inventory-report`** catalogs every SQL/ORM query the project runs.

- Design doc: [DESIGN.md](./DESIGN.md)
- User manuals: overview **[MANUAL.md](./MANUAL.md)** - per skill **[tuning-report](./MANUAL-tuning-report.md)** / **[inventory-report](./MANUAL-inventory-report.md)**
- **Report language**: output follows your conversation language (`report.language: auto`).

---

## Skills

| Skill | Invoke | What it does |
|-------|--------|--------------|
| **`tuning-report`** | `/query-inspector:tuning-report` | Extracts the SQL/ORM queries in your `git` changes (or the whole project) and **tunes** them ([manual](./MANUAL-tuning-report.md)) |
| **`inventory-report`** | `/query-inspector:inventory-report` | Extracts the project's queries (ORM-generated included) and **lists** them ([manual](./MANUAL-inventory-report.md)) |

Both skills share the same front end (collect changes -> extract queries -> reconstruct SQL) and guardrails, and differ only in what they produce. Run whichever fits, or both.<br>
`tuning-report` keeps incremental state and verifies previous suggestions, while `inventory-report` works over the whole project by default.

---

## ⚠️ Security note (read first)

Both skills can optionally **connect to a development DB and run `EXPLAIN` and other read-only queries** (`tuning-report`: plan-based tuning, `inventory-report`: to confirm index coverage).<br>
Please observe the following:

- **No production**: To keep from ever connecting to a production DB, the skill blocks `*prod*`/`*live*`/`*production*` host patterns by default, and a `host_allowlist` is recommended.
- **Read-only recommended**: When you specify a DB account, prefer a read-only one. The skill runs nothing but `SELECT`/`EXPLAIN` (enforced by guardrail code).
- **Never commit credentials to the project's repo**:
  - In the config file `.query-inspector.yml`, keep only the **variable name** of the connection URL, not the URL itself.
  - The `--db` connection URL goes **only into an environment variable or `.env`**. `.env` is a secrets file created in the project directory where the skill runs.
  - So that `.env` is never committed, the skill auto-registers it in the project's `.gitignore` - don't remove that entry.
- **DB access is opt-in**: By default it runs only static analysis, which needs no DB connection. The DB is touched only when you pass `--db <profile>`.

Full guardrails: [DESIGN.md section 7](./DESIGN.md).

---

## Highlights

1. Extracts only the **query-generating code** from your `git` changes (or the whole project); non-query changes are dropped early.
2. Takes explicit SQL as-is and **infers the SQL that ORM / dynamic queries will generate** (with a confidence label).
3. Works across **three tiers**: static heuristics -> schema context -> live-DB EXPLAIN.
4. **`tuning-report`** produces a report with severity, rationale, and **fix suggestions**; **`inventory-report`** produces a catalog with each query's **full body** and index coverage.
5. Neither ever edits your code.

---

## Install

**Install with the `claude` CLI** — register the marketplace and install.

```bash
claude plugin marketplace add jogakdal/query-inspector
claude plugin install query-inspector@query-inspector-marketplace
```

After install, invoke in a new session with `/query-inspector:tuning-report` or `/query-inspector:inventory-report`.

> - If you cloned the repo, the setup script also works: `bash query-inspector-setup.sh` (options `--project` / `--local`). On **Windows**, `query-inspector-setup.bat`.
> - The runtime scripts are all Python, so it works the same on mac/linux/Windows.
> - If the setup script won't run, grant execute permission (`chmod 755`) or run it via `bash`.

- **Plugin install**
  - Registers the marketplace (`query-inspector-marketplace`) and installs the plugin (both skills).
  - Invoke with **`/query-inspector:tuning-report`** or **`/query-inspector:inventory-report`**; update with `claude plugin update query-inspector@query-inspector-marketplace` (restart to apply).
  - The setup script file alone is enough (no repo clone needed).
  - Defaults to user-global; `--project` selects project-local (this project only), run **from the target project root**.
  - Requires the `claude` CLI; a public repo is fetched anonymously (no auth needed).
- **Local checkout (`--local`)**
  - Registers your cloned/forked checkout as the marketplace and installs from it - for offline or modified builds, no network.
  - There is no skill-copy install: the two skills share assets under the `/query-inspector:` namespace, which only resolves when the tree is loaded as a plugin.

Full install guide (method comparison, manual install): **[INSTALL.md](./INSTALL.md)** <br>
Usage, config, troubleshooting: overview **[MANUAL.md](./MANUAL.md)** or the per-skill manuals above.

---

## Requirements

**Basic use (Tier 1 / Tier 2) needs no extra install** - just `git` and `python3` (mac/linux) or `python`/`py` (Windows), standard library only. <br>
The runtime scripts are all Python, so it runs the same on **mac / Linux / Windows**. <br>
Most tuning (missing indexes, N+1, SQL dialect mismatches, anti-patterns) comes from Tier 1 / Tier 2.

| Tier | Needs |
|------|-------|
| **Tier 1** static heuristics (default) | nothing |
| **Tier 2** schema context | nothing (schema files / live-DB lookup) |
| **Tier 3** live-DB EXPLAIN (`--db`, opt-in) | MySQL: `mysql` CLI or `pymysql` / PostgreSQL: `psql` or `psycopg` / plus `PyYAML` |

Tier 3 is **driver-first with a `mysql` CLI fallback**, so it works with just the CLI even where pip is restricted. <br>
If neither the driver nor the CLI is present, only Tier 3 auto-degrades to Tier 2.

---

## 5-minute start

```bash
# 1) Copy the config template (optional - works with defaults)
cp .query-inspector.example.yml .query-inspector.yml

# 2) Stage changes and invoke (plugin install)
git add .
claude
> /query-inspector:tuning-report
```

| Command | What it does |
|---------|--------------|
| `/query-inspector:tuning-report` | changes since last tuning (asks for scope on first run) |
| `/query-inspector:tuning-report --all` | all query-related sources (ignores incremental baseline) |
| `/query-inspector:tuning-report --all --no-state` | full scan without saving state (one-off) |
| `/query-inspector:tuning-report --range main..HEAD` | a given range |
| `/query-inspector:tuning-report --db dev` | deepen with EXPLAIN via the `dev` profile (opt-in) |
| `/query-inspector:inventory-report` | catalog the project's queries instead of tuning (full by default) |
| `/query-inspector:tuning-report --version` | print installed version |
| `/query-inspector:tuning-report --help` | usage |

Details per skill: [tuning-report manual](./MANUAL-tuning-report.md) / [inventory-report manual](./MANUAL-inventory-report.md).

---

## Tuning depth (auto-degrade)

`tuning-report` tunes across three tiers (`inventory-report` uses Tiers 1-2 for index coverage):

- **Tier 1 - static heuristics** (no DB, always on): N+1, `SELECT *`, non-SARGable predicates, leading-wildcard LIKE, unbounded result sets, etc.
- **Tier 2 - schema context** (auto-detected DDL / entities / migrations, or `--db` live schema): index-coverage matching, concrete `CREATE INDEX` suggestions.
- **Tier 3 - live-DB EXPLAIN** (`--db`, opt-in): plan-based deep dive, before/after comparison.

With no schema it degrades to Tier 1; on DB failure to Tier 2, and the report says so.

---

## Report examples
### tuning-report

Results come as a **report**; your code is never edited (suggestions only). It includes **Action Items** so a developer - or that developer's AI - can start immediately.

A slice of a real report (incremental, 2nd run):

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

Note the **follow-up**: it remembers last run's suggestions and flags the two *still* not applied - even in files you didn't touch this run.

- **Terminal summary** - top N by severity.
- **Detail file** - `docs/query-inspector/tuning-reports/<timestamp>.md` (history/cache). Full example: [examples/sample-report.md](./examples/sample-report.md).

Each issue: source (`file:line`) / inferred SQL (+ confidence label `EXACT`/`INFERRED`/`AMBIGUOUS`) / last modifier (git blame) / rationale / fix suggestion / how to verify.

---

### inventory-report

`inventory-report` turns the project's queries into a **catalog** - no severity, no fix suggestions, just each query's **full body** and index coverage.

A slice of a real inventory:

```markdown
# Query Inventory - 2026-09-30
- Scope: whole project / Dialect: mysql / Schema source: SCHEMA-CONFIRMED
- Queries: 24 ( SELECT 18 / INSERT 3 / UPDATE 2 / DELETE 1 )   /   Confidence: EXACT 15 / INFERRED 7 / AMBIGUOUS 2

## Summary (by table)
| Table  | Queries | Type mix            | Index-uncovered |
|--------|---------|---------------------|-----------------|
| orders | 8       | SELECT 6 / UPDATE 2 | 1 (❌)          |
| member | 5       | SELECT 5            | 0               |

## Query list  (domain: order)
#### [order-03] Orders for a given user
- Source: OrderMapper.xml:42 (selectOrdersByUser) / Adapter: mybatis / Type: SELECT / Confidence: EXACT
- Target: orders / Access columns: WHERE user_id, ORDER BY created_at
- Index coverage: ❌ uncovered (no index on user_id)
- Query body:
      SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC;
```

Each query: purpose / source (`file:line`) / last modifier / adapter, type, confidence / target tables / access columns / index coverage (✅ covered / ❌ uncovered / ❓ schema unknown) / **full body**. Full format in the [inventory-report manual](./MANUAL-inventory-report.md).

---

## Accuracy limits

ORM dynamic queries can't be reconstructed 100%. So every inferred query carries a confidence label, and `AMBIGUOUS` items come with "how to verify the real SQL" (e.g. Hibernate `show_sql`).

---

## Extending (new stacks)

**Python (Django / SQLAlchemy)** ships adapters too, though not as thoroughly validated as the primary stacks (e.g. `stacks: [python-django]`). **Node (Prisma/TypeORM) and .NET (EF Core/Dapper) are the next candidates**; the adapter structure lets them be added without touching the core (just `references/adapters/<stack>.md`), so contributions are welcome. -> [references/adapters/_template.md](./references/adapters/_template.md)

Contributions welcome - see [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## License

[MIT](./LICENSE) - free for commercial use, modification, and redistribution; keep the copyright and license notice.
