query-inspector - inspect the SQL/ORM queries in your changes. Two skills:

  /query-inspector:tuning-report      tune before commit - missing indexes, N+1s, anti-patterns
  /query-inspector:inventory-report   catalog project queries (purpose / tables / body / index coverage)

Scope (default: incremental since last tuning / asks on first run):
  --all            force all query-related sources
  --staged         staged changes only
  --range <rev>    a given range (e.g. main..HEAD, HEAD~3)
  --files <paths...> specific files only
  --continue       resume an in-progress progressive full scan at the next domain

Tuning depth (tuning-report; default: auto / degrades with the environment):
  --depth static   static heuristics only (Tier 1)
  --depth schema   + schema index matching (Tier 2)
  --depth explain  + live-DB EXPLAIN (Tier 3)

Other (both skills):
  --db <profile>   deepen with live-DB EXPLAIN (opt-in / production blocked / read-only)
  --dialect <d>    force SQL dialect: mysql|mariadb|postgresql|oracle|ansi (default: auto-detect)
  --lang <code>    force output language: ko|en|ja|zh ... (default report.language=auto)
  --no-state       run once without reading/writing state (tuning-report)
  --reset-state    reset state (next run is full)
  --no-update-check  skip the new-version check this run
  --version        print the installed version (e.g. query-inspector v1.0.0 (plugin))
  --help, -h       this help

What they do:
  tuning-report  - extracts SQL/ORM queries from your changes and catches missing
                   indexes (-> CREATE INDEX suggestions), N+1s, non-SARGable predicates,
                   dialect mismatches, and more; verifies whether previous suggestions
                   were applied (follow-up). Report + Action Items; never edits code.
  inventory-report - lists the project's queries (purpose, target tables, full body,
                   index coverage). Full by default; batch large repos with --continue.

Outputs:
  / terminal summary (top N by severity)
  / detail report    docs/query-inspector/tuning-reports/<timestamp>.md            (tuning-report)
  / query inventory  docs/query-inspector/inventory-reports/inventory-<timestamp>.md  (inventory-report)

Examples:
  /query-inspector:tuning-report                    # changes since last tuning
  /query-inspector:tuning-report --all              # review everything
  /query-inspector:tuning-report --range main..HEAD # branch diff
  /query-inspector:tuning-report --db dev           # deepen with EXPLAIN via the dev DB
  /query-inspector:inventory-report                 # project query catalog
  /query-inspector:inventory-report --db dev        # catalog with index coverage confirmed via DB

Requirements: git / python3 (Windows: python or py) - the runtime scripts are all
          Python, so it works the same on mac/linux/Windows (no bash). Only Tier 3
          (--db) additionally needs a DB client - MySQL: mysql CLI or pymysql;
          PostgreSQL: psql or psycopg; plus PyYAML.
Config: .query-inspector.yml (template: .query-inspector.example.yml)
Install/details: MANUAL.md   (Windows: query-inspector-setup.bat, mac/linux: query-inspector-setup.sh)
