# Install

**English** | [한국어](./INSTALL.ko.md)

> The full install reference - the setup script and the manual steps it wraps.
> After installing, see **[MANUAL.md](./MANUAL.md)** for usage, options, configuration, Tier 3, and troubleshooting.

---

## Quick install

```bash
# Install the plugin (from the public marketplace)
claude plugin marketplace add jogakdal/query-inspector
claude plugin install query-inspector@query-inspector-marketplace

# Or via the setup script (after cloning the repo)
bash query-inspector-setup.sh              # user-global (default) -> /query-inspector:tuning-report
bash query-inspector-setup.sh --project    # project-local (this project only)
bash query-inspector-setup.sh --local      # register THIS checkout as the marketplace (clone/fork/offline)
```

On **Windows**, run `query-inspector-setup.bat` with the same options. The runtime scripts are all Python, so it works the same on mac / Linux / Windows (no bash needed at runtime).

---

## Plugin-only (why there's no `--skill` copy)

query-inspector installs **as a plugin**, not as a hand-copied skill folder. It ships **two skills** (`tuning-report`, `inventory-report`) that share `references/`, `scripts/`, and `assets/` through `${CLAUDE_PLUGIN_ROOT}`, and both are invoked under the `/query-inspector:` namespace. That layout only resolves when Claude Code loads it as a plugin - copying one skill folder into `~/.claude/skills/` breaks the shared-asset paths and the namespace, so there is no skill-copy install.

If you cloned or forked the repo (or need an offline / modified build), use **`--local`**: it registers your local checkout as the marketplace source and installs the plugin from it - same result, no network.

---

## Requirements

- **Basic (Tier 1 / 2):** the `claude` CLI, `git`, and `python3` (mac/linux) or `python`/`py` (Windows) - standard library only, nothing to pip-install.
- **Tier 3 (live-DB EXPLAIN, optional):** for MySQL, the `mysql` CLI (usually preinstalled) or `pymysql`; for PostgreSQL, `psql` or `psycopg`; plus `PyYAML` for config parsing.
- A **private** repo needs git auth (SSH key / PAT (Personal Access Token)); a **public** repo needs none.

---

## A. Script install (recommended)

The setup script automates section B for you. If you cloned the repo it's already at the root; otherwise download just the script file - [`query-inspector-setup.sh`](https://raw.githubusercontent.com/jogakdal/query-inspector/main/query-inspector-setup.sh) (on Windows, [`query-inspector-setup.bat`](https://raw.githubusercontent.com/jogakdal/query-inspector/main/query-inspector-setup.bat)). Run it where you downloaded it, or at the target project root.

```bash
bash query-inspector-setup.sh              # user-global
bash query-inspector-setup.sh --project    # project-local - run from the project root, or pass --project <path>
bash query-inspector-setup.sh --local      # use THIS checkout as the marketplace source (clone/fork/offline/verify)
```

- **default** - registers the public marketplace (`jogakdal/query-inspector`) and installs the plugin user-global.
- **`--project [DIR]`** - installs into one project only (`--scope local`); run from the project root or pass the path.
- **`--local`** - registers the directory the script lives in as the marketplace (it must contain `.claude-plugin/marketplace.json`), then installs from it. Combine with `--project` for a project-local install straight from your checkout.

Invoke `/query-inspector:tuning-report` or `/query-inspector:inventory-report` in a new session.

### Windows

Run `query-inspector-setup.bat` from `cmd` (or double-click). Same options: `--project`, `--local`.

---

## B. Manual install (no script)

The setup script is just a wrapper around the steps below - do them by hand if you'd rather not run the script, or to see exactly what it does.

### B-1. From the public marketplace

```bash
# 1) Register this repo as a marketplace
claude plugin marketplace add https://github.com/jogakdal/query-inspector
#    (a public repo also accepts the owner/repo shorthand: jogakdal/query-inspector)
#    Private repo: use the SSH URL instead -
#    claude plugin marketplace add git@github.com:jogakdal/query-inspector.git

# 2) Install the plugin
claude plugin install query-inspector@query-inspector-marketplace -y --scope user
#    Project-local instead: run from the project root and use --scope local
```

Invoke `/query-inspector:tuning-report` in a new session.

### B-2. From a local checkout (clone / fork / offline)

```bash
# 1) Get the files
git clone --depth 1 git@github.com:jogakdal/query-inspector.git

# 2) Register the checkout directory as a marketplace (it ships .claude-plugin/marketplace.json)
claude plugin marketplace add ./query-inspector

# 3) Install the plugin from it
claude plugin install query-inspector@query-inspector-marketplace -y --scope user
#    Project-local instead: run from the project root and use --scope local
```

This is exactly what `query-inspector-setup.sh --local` does - use it to run a modified or offline build without pushing anywhere. Invoke `/query-inspector:tuning-report`.

> **Why register the whole checkout, not copy a skill folder?** The two skills (`tuning-report`, `inventory-report`) share `references/`/`scripts/`/`assets/` through `${CLAUDE_PLUGIN_ROOT}`, and both live under the `/query-inspector:` namespace - which only resolves when the tree is loaded as a plugin.

---

## Update / uninstall

- **Update** - `claude plugin update query-inspector@query-inspector-marketplace` (restart Claude Code to apply). To refresh the catalog first: `claude plugin marketplace update query-inspector-marketplace`. For a `--local` install, `git pull` in the checkout, then `claude plugin marketplace update ...` and `claude plugin update ...`.
- **Uninstall** - `claude plugin uninstall query-inspector@query-inspector-marketplace`.
- **Auto-update** - the skill also checks for a new version at runtime; see [the tuning-report manual, section 8](./MANUAL-tuning-report.md) (same for both skills).

---

## Verify

```bash
/query-inspector:tuning-report --version    # e.g. query-inspector v1.0.1 (plugin)
/query-inspector:tuning-report --help
```

A **fresh session** is needed after install for the plugin to load.

-> Usage, options, configuration, Tier 3, troubleshooting: **[MANUAL.md](./MANUAL.md)**.
