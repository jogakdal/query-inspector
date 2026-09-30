# Privacy Policy

**English** | [한국어](./PRIVACY.ko.md)

query-inspector is a **local developer tool**. It does not collect, store, or transmit personal data.

## What it does
- Analyzes the SQL / ORM queries in your local git repository (query text, schema structure).
- Writes reports to disk under your project (`docs/query-inspector/`).

## Data handling
- **No personal data collected.** It does not read end-user or customer records. The optional Tier 3 runs `EXPLAIN` (query plans) only - it never reads table rows.
- **No external transmission.** All analysis runs locally. When you opt into Tier 3 with `--db`, the database connection URL is read only from a local environment variable or `.env` and is used solely to connect to your own development database. It is never written to reports or logs, and never sent anywhere else.
- **Last-modifier attribution** uses your local `git blame` (commit author) purely as code metadata in the report; it is not transmitted.
- **Update check** contacts the plugin's git remote once a day to compare versions - no user data is sent. It can be turned off with `--no-update-check`.
- **Nothing received from Claude is retained** - there is no server or backend.

## Contact
Questions or concerns: https://github.com/jogakdal/query-inspector/issues
