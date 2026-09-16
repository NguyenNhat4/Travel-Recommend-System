# Test fixtures

Committed on purpose, which is why `.gitignore` excludes the raw cache **by
path** (`data/raw/`) rather than by extension: a `*.gz` rule would delete this
corpus and `pytest` would then pass because it had nothing left to check.

## What belongs here

Small, saved responses that let the parsers be tested with **no network**. Add
one with:

    python -m cli save-fixture --raw-page-id <id> --name <short-name>

That copies the cached page out of `data/raw/` and writes a `.url.txt` beside it
recording where it came from.

## Third-party content

These files are copies of third-party pages, retained locally so a parser can be
re-tested without re-fetching. They are not redistributed, and only the fields
listed in `collectors/base.py::PAYLOAD_CONTRACT` are ever extracted from them.
Review text and reviewer names are dropped at extraction time
(`extract.jsonld_pick`) per spec section 5.4 — so do not add a fixture whose
only purpose is to carry review content.
