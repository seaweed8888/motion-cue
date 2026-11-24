# Repository instructions

Use the `graphify`, `caveman` and balanced `unslop` skills when available. Keep
responses concise and technically complete. Existing user instructions take
precedence over these defaults.

## Before changing files

- Check the working tree and preserve unrelated edits and user files.
- If `graphify-out/graph.json` exists, query Graphify before browsing source or
  changing repository files. Refresh the graph after code changes or file moves;
  documentation moves also need the semantic document paths refreshed.
- Read the nearest component `README.md`. For UI work, also read root
  `PRODUCT.md` and `DESIGN.md` and follow the Impeccable skill when available.

## Where files belong

| Content | Location |
|---|---|
| Project overview, installation and entry points | Root `README.md` |
| Instructions for agents | Root `AGENTS.md`; nested instructions only when a component needs different rules |
| Product and design context used by Impeccable | Root `PRODUCT.md` and `DESIGN.md` |
| Component setup and usage | That component's `README.md` |
| Shared contracts, feature definitions and hardware decisions | `docs/reference/` |
| Measurements, experiment logs, audits and review reports | `docs/reports/` |
| Superseded plans and handoffs | `docs/archive/`, with a historical notice |
| Design mockups and captured previews | `docs/mockups/` and `docs/previews/` |
| Tool-owned review history and settings | `.impeccable/`; keep its generated layout |
| Generated knowledge graph and caches | `graphify-out/`; keep ignored |

Keep source code in its existing component: desktop/MQTT in `monitoring/`, ML
tools in `training/`, device code in `firmware/`, and shared executable contracts,
labels and examples in `shared/`. Tests belong in `tests/`; recordings and model
artifacts belong in `data/` and `models/` under the existing ignore rules.

## Keep documentation organized

- Do not add other root-level Markdown files or put standalone specifications
  and reports beside source code. Use the table above.
- Use lowercase kebab-case for new documentation filenames, except conventional
  `README.md`, `AGENTS.md`, `PRODUCT.md` and `DESIGN.md`.
- Update the existing document for a topic rather than creating duplicate
  summaries, progress notes or handoffs. Date measured results and distinguish
  synthetic tests from real hardware measurements.
- Add new human-maintained documents to `docs/README.md`. Link to the original
  source of truth rather than copying its contents into several READMEs.
- When moving a file, update live references across the repository, including
  relative links and configuration paths. Preserve historical examples and
  tool-owned snapshots as historical records; label archived documents clearly.
- Check local Markdown links and search for obsolete paths after moves. Run
  tests when executable code or behavior changes; documentation-only moves need
  link/path validation, not the full runtime suite.
