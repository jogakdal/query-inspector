# Contributing

Thanks for your interest in improving **query-inspector**. This skill is intentionally
small and self-contained; contributions that keep it focused are very welcome.

## Development & tests

The runtime scripts are plain Python (no third-party deps for the core), so you can
run the checks anywhere `git` and Python are available:

```bash
python3 -m py_compile scripts/*.py        # syntax
python3 scripts/db_guard.py --self-test   # DB guardrail unit tests
bash tests/run_tests.sh                   # deterministic regression (classification, incremental, goldens)
```

- The skill's extraction/heuristic *judgement* is performed by the LLM, so it is not
  unit-tested here; the golden files under `tests/expected/` and the `evals/` suite
  (`claude plugin eval`) cover that side.
- Tier 3 (live-DB EXPLAIN) is opt-in and guarded by `scripts/db_guard.py`. Never point
  tests at a production database.

## Adding a stack adapter

New stacks (Python/Django, Node/Prisma, ...) need no core changes - add
`references/adapters/<stack>.md` following [`references/adapters/_template.md`](./references/adapters/_template.md).

## Bilingual docs (English canonical + Korean)

User-facing docs ship in two languages:

- `README.md` / `MANUAL.md` / `MANUAL-tuning-report.md` / `MANUAL-inventory-report.md` - **English (canonical / source of truth)**
- `README.ko.md` / `MANUAL.ko.md` / `MANUAL-tuning-report.ko.md` / `MANUAL-inventory-report.ko.md` - **Korean**
- `assets/help.md` - English; the skill renders it in the user's language at `--help` time.

**When you change a user-facing doc, update both languages in the same change.**
Two rules:

1. **Sync the *content*, not the sentences.** Write each language as a natural document
   in that language. The Korean version must not read like a word-for-word translation
   of the English - and vice versa.
2. **English is the source of truth.** If the two ever drift, the English version wins;
   fix the other to match in meaning.

`SKILL.md` and `references/**` are LLM-facing instructions and are kept in one language
(Korean is fine) - the LLM understands either; see [`references/i18n.md`](./references/i18n.md).

## Commit messages

Write commit messages in **English** in this (public) repository, so the history stays
consistent with the English-canonical docs and readable to outside contributors. Keep the
subject short and imperative (e.g. "Add ...", "Fix ..."); add a brief body when the change
needs context. (The internal downstream repository uses Korean commit messages - the two
repos are independent.)

## Versioning

Bump `version` in both `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
together when you change skill content - `claude plugin update` compares versions, so an
un-bumped change won't roll out. Note the change in [`CHANGELOG.md`](./CHANGELOG.md).

## License

By contributing you agree that your contributions are licensed under the [MIT License](./LICENSE).
