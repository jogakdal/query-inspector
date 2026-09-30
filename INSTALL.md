# Install

**English** | [한국어](./INSTALL.ko.md)

> The full install reference - both the setup script and the manual steps it wraps, for both install methods (plugin / skill).
> After installing, see **[MANUAL.md](./MANUAL.md)** for usage, options, configuration, Tier 3, and troubleshooting.

---

## Quick install

```bash
# Install the plugin (recommended)
claude plugin marketplace add jogakdal/query-inspector
claude plugin install query-inspector@query-inspector-marketplace

# Or via the setup script (after cloning the repo)
bash query-inspector-setup.sh              # plugin, user-global (default) -> /query-inspector:tuning-report
bash query-inspector-setup.sh --project    # plugin, project-local (this project only)
bash query-inspector-setup.sh --skill      # install as a skill (user-global)
```

On **Windows**, run `query-inspector-setup.bat` with the same options. The runtime scripts are all Python, so it works the same on mac / Linux / Windows (no bash needed at runtime).

---

## Plugin vs. skill

|  | Plugin (default) | Skill (`--skill`) |
|---|---|---|
| Managed by | Claude Code's plugin system | plain files under `~/.claude/skills/` |
| Updates | `claude plugin update ...` (easy) | re-copy the files |
| Prerequisite | the `claude` CLI | just a file copy (git only to fetch if not local) |
| Files needed | just the one setup script (the rest is fetched from the marketplace) | the repo files |
| Invoke | `/query-inspector:tuning-report` / `:inventory-report` | `/query-inspector:tuning-report` / `:inventory-report` |

The **plugin method is recommended** for its easy updates.

---

## Requirements

- **Basic (Tier 1 / 2):** `git`, and `python3` (mac/linux) or `python`/`py` (Windows) - standard library only, nothing to pip-install.
- **Tier 3 (live-DB EXPLAIN, optional):** for MySQL, the `mysql` CLI (usually preinstalled) or `pymysql`; for PostgreSQL, `psql` or `psycopg`; plus `PyYAML` for config parsing.
- A **private** repo needs git auth (SSH key / PAT (Personal Access Token)); a **public** repo needs none.

---

## A. Script install (recommended)

The setup script automates section B for you. If you cloned the repo it's already at the root; otherwise download just the script file - [`query-inspector-setup.sh`](https://raw.githubusercontent.com/jogakdal/query-inspector/main/query-inspector-setup.sh) (on Windows, [`query-inspector-setup.bat`](https://raw.githubusercontent.com/jogakdal/query-inspector/main/query-inspector-setup.bat)). Run it where you downloaded it, or at the target project root.

### Plugin (default)

```bash
bash query-inspector-setup.sh              # user-global
bash query-inspector-setup.sh --project    # project-local - run from the project root, or pass --project <path>
```

Registers the marketplace and installs the plugin. Invoke `/query-inspector:tuning-report` or `/query-inspector:inventory-report` in a new session.

### Skill (`--skill`)

```bash
bash query-inspector-setup.sh --skill              # user-global -> ~/.claude/skills/query-inspector/
bash query-inspector-setup.sh --skill --project    # project-local -> <project>/.claude/skills/query-inspector/
bash query-inspector-setup.sh --skill --force      # overwrite an existing install without asking
```

Copies the whole plugin tree (both skills + shared assets) into one skills directory. If the files aren't present locally, the repo is cloned automatically.

### Windows

Run `query-inspector-setup.bat` from `cmd` (or double-click). Same options: `query-inspector-setup.bat --project`, `--skill`, `--force`.

---

## B. Manual install (no script)

The setup script is just a wrapper around the steps below - do them by hand if you'd rather not run the script, or to see exactly what it does.

### B-1. Plugin, manually

```bash
# 1) Register this repo as a marketplace
claude plugin marketplace add https://github.com/jogakdal/query-inspector
#    (a public repo also accepts the owner/repo shorthand)
#    Private repo: use the SSH URL instead -
#    claude plugin marketplace add git@github.com:jogakdal/query-inspector.git

# 2) Install the plugin
claude plugin install query-inspector@query-inspector-marketplace -y --scope user
#    Project-local instead: run from the project root and use --scope local
```

Invoke `/query-inspector:tuning-report` in a new session.

### B-2. Skill, manually (mac / Linux)

```bash
# 1) Get the files
git clone --depth 1 git@github.com:jogakdal/query-inspector.git

# 2) Copy the WHOLE plugin tree into one skills directory
mkdir -p ~/.claude/skills/query-inspector
cp -R query-inspector/{skills,.claude-plugin,references,scripts,assets,.query-inspector.example.yml} \
      ~/.claude/skills/query-inspector/

# 3) Make the scripts executable
chmod +x ~/.claude/skills/query-inspector/scripts/*.py
```

Project-local: copy into `<project>/.claude/skills/query-inspector/` instead. Invoke `/query-inspector:tuning-report`.

> **Why copy the whole root, not just a skill folder?** The two skills (`tuning-report`, `inventory-report`) share `references/`/`scripts/`/`assets/` through `${CLAUDE_PLUGIN_ROOT}`, so those must sit alongside `skills/`.

---

## Update / uninstall

- **Plugin** - update: `claude plugin update query-inspector@query-inspector-marketplace` (restart Claude Code to apply). To refresh the catalog first: `claude plugin marketplace update query-inspector-marketplace`. Uninstall: `claude plugin uninstall query-inspector@query-inspector-marketplace`.
- **Skill** - update: re-run the copy (or `--skill --force`). Uninstall: delete the `~/.claude/skills/query-inspector/` directory.
- **Auto-update** - the skill also checks for a new version at runtime; see [the tuning-report manual, section 8](./MANUAL-tuning-report.md) (same for both skills).

---

## Verify

```bash
/query-inspector:tuning-report --version    # e.g. query-inspector v1.0.0 (plugin)
/query-inspector:tuning-report --help
```

A **fresh session** is needed after install for the plugin/skill to load.

-> Usage, options, configuration, Tier 3, troubleshooting: **[MANUAL.md](./MANUAL.md)**.
