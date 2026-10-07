# query-inspector - User Manual

**English** | [한국어](./MANUAL.ko.md)

`query-inspector` provides **two skills** for optimizing the queries in your project. <br>
Invoked manually, they generate a **tuning report** or a **query inventory** over the whole project or just your changes.<br>
The runtime scripts are all Python, so it works the same on **mac / Linux / Windows**.

Other documents:

> Intro/positioning: [README.md](./README.md) <br>
> Full install guide: [INSTALL.md](./INSTALL.md)<br>
> Design: [DESIGN.md](./DESIGN.md)<br>Change history: [CHANGELOG.md](./CHANGELOG.md)

---

## Skills

|          Skill           | What it does | Manual |
|:------------------------:|--------------|--------|
|   **`tuning-report`**    | Extracts the SQL / ORM queries in your changes and generates a **tuning** report - missing indexes / N+1s / anti-patterns. Incremental with follow-up. | **[MANUAL-tuning-report.md](./MANUAL-tuning-report.md)** |
| **`inventory-report`**   | Extracts the project's queries and generates a query **list** - purpose / tables / full query body / index coverage. No tuning. | **[MANUAL-inventory-report.md](./MANUAL-inventory-report.md)** |

```
/query-inspector:tuning-report       # tune the queries in your changes (incremental by default)
/query-inspector:inventory-report    # catalog the project's queries (full by default)
```

Both are invoked by namespace regardless of install method, and both need a **new Claude Code session** to appear after install.

### Choosing a skill

- **Improving query performance** - missing indexes / N+1s / anti-patterns -> `tuning-report`.
- **Seeing every query a project runs** - full bodies + index coverage -> `inventory-report`.

They are independent; run whichever fits, or both. `tuning-report` keeps incremental state and verifies previous suggestions; `inventory-report` works over the whole project by default.

---

## Shared behavior

Each item below is summarized here and covered in full in each skill's manual.

- **Install**: one setup script (plugin install; `--local` to install from your own checkout). Full guide in [INSTALL.md](./INSTALL.md); short version in section 2 of either skill manual.
- **Option scope**:
  - Common options: `--all` / `--range` / `--files` / `--staged` / `--continue` / `--dialect` / `--lang` / `--version` / `--help`
  - Tuning-only options: `--depth` / `--db` / `--no-state` / `--reset-state`
- **Live-DB access is opt-in**:
  - Static analysis by default (Tier 1, Tier 2).
  - Only `--db <profile>` touches a database - to run EXPLAIN (Tier 3) - and even then **production is blocked** and access is **read-only**.
  - Credentials go through an env var / `.env` only, never the config file or the report.
- **Configuration**: set config values in `.query-inspector.yml`.
  - Copy it from `.query-inspector.example.yml`; works with defaults.
  - The report root is the `report.dir` value (default `docs/query-inspector`): tuning reports go under `tuning-reports/`, inventories under `inventory-reports/`.
- **Auto-update**: both skills check once a day at runtime; details in section 8 of either manual.

---

## Further reading

- **[MANUAL-tuning-report.md](./MANUAL-tuning-report.md)** - tuning usage, options, 3 tiers, Tier 3 live-DB EXPLAIN, report format, configuration, FAQ.
- **[MANUAL-inventory-report.md](./MANUAL-inventory-report.md)** - inventory usage, options, the catalog pipeline, index coverage, report format, configuration, FAQ.
- **[INSTALL.md](./INSTALL.md)** - plugin vs. skill, manual install, verification.

The full heuristics catalog and design live in `references/` and [DESIGN.md](./DESIGN.md).
