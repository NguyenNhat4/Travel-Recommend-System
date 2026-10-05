# Repo problem list (2026-10-05)

- Branch `feat/agent`, commit `585fcfc`. Local Postgres + Weaviate, seeded catalog.
- Each item has a priority, an area, the evidence I saw, and a fix idea. Fix one item at a time and tick its box.
- Each fix needs its own `history/` entry (AGENTS.md §5). A fix that changes PRD behaviour needs an approved proposal first (§8).
- Items 1–19 I verified myself today. Items 20–23 are already documented and wait for a decision. Items 24–27 are reported in history but need VM/GCP access to verify.

## What passes

| Check | Result |
|---|---|
| Backend `pytest tests/unit tests/architecture tests/contract` | 1,143 passed (4 min). Integration tests not run. |
| Frontend `tsc --noEmit` | Clean |
| Frontend `vitest run` | 576 / 576 passed |
| Frontend `eslint .` | 0 errors, 2 warnings (item 12) |
| `validate_contract.py` | PASS |
| `db/verify_insider.sql` | All PASS |
| `db/verify.sql` | 2 FAIL, both caused by a local test account (item 19), not by the seed |
| Secret scan of tracked files | No keys found. `.env` is not tracked. |

## High

### - [ ] 1. Combos with `returnDate = "15/10"` break the assistant in 7 cities

- **Area:** data (collector), with the effect in the agent. FR-AGT-02, FR-AGT-03, AC-AGT-01.
- **Evidence:**
  - 33 combos have `attributes.returnDate = "15/10"`. The contract says `format: date` (`src/shared/contracts/schemas/catalog.yaml:114`).
  - The agent validates each tool response against the contract (`application/itinerary/tool_contracts.py`). A response that contains one of these combos fails with `INVALID_TOOL_RESPONSE`.
  - Guest, Search "Cần Thơ": 6 bad combos in the results, so the response is rejected.
  - P1 demo account, recommendations for Đà Lạt, Huế, Cần Thơ, Quy Nhơn: rejected each time.
  - The error is not retryable. The turn ends as FALLBACK or FAILED (see item 3).
- **Cities:** Huế, Quy Nhơn, Đà Lạt, Cần Thơ (6 each); Hạ Long, Đà Nẵng, TP. Hồ Chí Minh (3 each).
- **Fix idea:** write ISO dates in `src/data_collection/collectors/trip_combos.py`. Make `seed/load_products.py` and `fresh_catalog_db.py` repair or reject non-ISO dates. Add a check to `db/verify.sql`. The root cause was already noted in `history/2026-10-02-fallback-neu-ly-do-that.md`.

### - [ ] 2. Recommendations remove bought categories for the wrong city

- **Area:** recommendation engine, with the effect in the agent and the product page. FR-REC-02, AC-AGT-01.
- **Evidence and fix:** `docs/plan/2026-10-05-fix-category-exclusion-other-city.md`. It is waiting for your review.

### - [ ] 3. One bad recommendation response fails the whole assistant turn

- **Area:** agent. FR-AGT-02, AC-AGT-01.
- **Evidence:**
  - Logged-in users always call `get_recommendations` (`agents/runtime_dependencies.py:52`, `steps/tool_planning.py:271`).
  - `steps/evaluation.py` `_decision` turns any non-retryable tool error into `fallback`, even when Search found products.
  - Only Similar has a soft-error rule (`_soft_similar_error`). Recommendation items are only a backup in the plan (`domain/itinerary/planning.py:166`), but a bad recommendation response still fails the turn.
  - Item 1 shows a real case.
- **Fix idea:** when Search succeeded, treat a `get_recommendations` error as soft: log it and continue without recommendations.

### - [ ] 4. Product cards do not show the "because" reason

- **Area:** frontend. FR-REC-03, AC-REC-01 ("mỗi thẻ sản phẩm hiển thị lý do `because` tương ứng").
- **Evidence:**
  - `components/common/ProductCard.tsx:38-40` receives `because`, `strategy` and `excludedVerticals`, then never uses them.
  - The `BecauseLine` render was removed in commit `b7bb4ab` (21/09). That commit's message is about OSRM route tests, so the removal looks accidental.
  - `BecauseLine.tsx` is now unused. The Home page shows only one "why" popover for the whole block (`recommendations[0].because`).
- **Fix idea:** render `BecauseLine` in `ProductCard` when `because` is not empty. Add a test so this does not disappear again.

## Medium

### - [ ] 5. Unhandled exceptions return a plain-text 500

- **Area:** backend. Contract Error Envelope (`docs/prd/api-contract.md` principles), NFR-REL.
- **Evidence:**
  - `api/errors.py:103` registers handlers only for known error types. There is no handler for `Exception`.
  - Test: the real `app` with `app.state.recommend = None` (RecSys still loading). `GET /api/v1/recommendations` returns `500 text/plain "Internal Server Error"`.
  - `/similar` returns 503 `SEARCH_UNAVAILABLE` in the same state.
- **Fix idea:** add a catch-all handler that returns the `INTERNAL_ERROR` envelope with `requestId`. Optionally make `/recommendations` return 503 like `/similar`, but that needs a contract change: its path lists only 400/401/500.

### - [ ] 6. Three golden dataset tests fail

- **Area:** agent evaluation. NFR-REL-01 (golden eval).
- **Evidence:** `pytest src/evaluation/tests` gives 3 failed, 62 passed:
  - `test_has_exactly_one_case_per_category_with_unique_ids`: 79 cases in 14 categories.
  - `test_a_start_date_question_is_answered_before_the_expected_result`.
  - `test_clear_requests_state_their_start_date_with_a_placeholder_and_check_the_extraction`.

  The dataset was replaced in commit `1dcaf91`; the tests still check the old rules. Several history entries since 30/09 note them as "fail sẵn" (already failing).
- **Fix idea:** update the tests to the new dataset rules, or fix the dataset. Decide which rules are still wanted.

### - [ ] 7. All Hà Nội hotels have a one-day sale window (local DB)

- **Area:** data. AGENTS.md §6.2 (30-day window from `as_of`).
- **Evidence:** all 529 Hà Nội hotels have `available_from = 2026-10-15`, `available_to = 2026-10-16`. An assistant plan for Hà Nội on any other date drops every hotel (`PRODUCT_DROPPED_DATE`). Reported to Data on 25/09 and still true locally.
- **Fix idea:** check the source data and loader for Hà Nội hotels. Check staging too; I only checked the local DB.

### - [ ] 8. The "Hoàn thiện chuyến {city}" block shows for any city

- **Area:** frontend. FR-REC-02.
- **Evidence (code only, not tested in a browser):**
  - `components/detail/ProductDetailView.tsx:399` shows the block when `trip.destination === product.destination`.
  - The engine always echoes the requested destination, so this condition is always true.
- **Fix idea:** also require `trip.strategy === 'cross_vertical'`. This is best done together with item 2.

### - [ ] 9. Recommendation spec and code disagree on 10 points

- **Area:** recommendation. FR-REC-01–04.
- **Evidence:** table in `docs/guide/recommendation-system-ste100.md` §11. It covers:
  - event weights;
  - `tripFactor`;
  - the score formula;
  - the diversity cap;
  - the dormant threshold (90 vs 180 days);
  - `exclusionRelaxed`;
  - `homeCity`;
  - the user vector cache;
  - the 500-event limit.
- **Fix idea:** for each point, either update spec §4 to match the code (code follows the PRD) or change the code. Item 10 is one of them.

### - [ ] 10. `events_for_user` reads all events of a user with no limit

- **Area:** recommendation, NFR-PERF (spec §7.1: 300 ms p95, maximum 500 events).
- **Evidence:** `infrastructure/cdp/postgres_cdp_reader.py:112` has no `LIMIT`. The local test account already has 222 events. `application/recommendation/history.py` `load_history` (with the 500 limit) is used only by its own test.
- **Fix idea:** add `LIMIT 500` (newest first). Then delete or use `load_history`.

### - [ ] 11. `app.search_logs` is never written

- **Area:** backend search. NFR-PERF-03 (query cache prewarm).
- **Evidence:** only a reader exists (`infrastructure/persistence/postgres_search_logs.py`). No code inserts rows. Prewarm "head queries" are always empty, so only the 131 gold questions are prewarmed.
- **Fix idea:** write one row for each `/search` call, or remove the head-query part. History notes this has no FR yet, so ask before you build it.

## Low / cleanup

### - [ ] 12. Two lint warnings in `ItineraryMap.tsx`

- `src/frontend/src/components/assistant/ItineraryMap.tsx:254` and `:404`: `useEffect` is missing the dependency `getAllPoints`.

### - [ ] 13. Dead code

- `application/recommendation/history.py` (`load_history`) is used only by its test (see item 10).
- `components/common/BecauseLine.tsx` is unused until item 4 is fixed.
- `ProductCard` props `because`, `strategy`, `excludedVerticals` are unused until item 4 is fixed.

### - [ ] 14. `WhyPopover` has misleading default props

- `components/common/WhyPopover.tsx:20-22` defaults to `strategy='cross_vertical'`, `excludedVerticals=['hotel']` and `destination='Nha Trang'`.
- A caller that forgets a prop shows "Chuyến Nha Trang của bạn đã có khách sạn" to a user who never booked one.
- The text also always talks about hotels and flights, whatever the excluded category is.
- **Fix idea:** make these props required or default to neutral text.

### - [ ] 15. `itinerary.title` is never filled

- The contract and `agents/models.py:102` have the field, but no backend code sets it.
- The frontend falls back to `message`, then to a fixed text (`context/assistantState.ts:100`).

### - [ ] 16. Documents inside `src/` (AGENTS.md §7)

- `src/evaluation/agent/agent-test-cases-nhat.md` (yours, committed in `1dcaf91`): move it to `docs/spec/agent/`. History 02/10 already noted this.
- `src/frontend/AGENTS.md` and `src/frontend/CLAUDE.md` are Next.js-generated agent rules. Keep them, but add them to the §7 exceptions, or remove them.

### - [ ] 17. `src/evaluation/README.md` does not exist

- AGENTS.md §1.2 tells agents to read it, and notes it is missing. Write a short one: folders, how to run golden, recsys_bench and search_bench.

### - [ ] 18. 59 history entries still say "Trạng thái: dang dở" (unfinished)

- Many are proposals that were later applied, archived or deleted. AGENTS.md §1.1 tells agents to read every unfinished entry in scope, so this costs time and misleads.
- **Fix idea:** history entries can't be rewritten, but the README allows adding a `Bị thay thế bởi: …` line. Add that line where an entry has a successor, or write one cleanup entry that lists the closed ones.

### - [ ] 19. Local `db/verify.sql` fails after manual testing

- `profiles = 2000` (2001) and `max events per user <= 15` (222) both come from the local test account `VPWXJ0YZ00SN4RY`, created 30/09.
- Not a repo bug. Run `make demo-db-reset` before a demo.

## Needs a decision (already documented)

### - [ ] 20. Proposal waiting for approval

- `docs/prd/update/2026-10-02-hoi-tiep-khi-cau-hoi-bi-cat-ngang.md` (agent, AC-AGT-01).

### - [ ] 21. Persona sets differ between PRD and DDL

- AGENTS.md §6.4: `P1_frequent…P4_no_history` in DDL vs `P1_family…P4_deal` in PRD. Needs a proposal.

### - [ ] 22. `docs/prd/api-contract.md` examples differ from the OpenAPI contract

- AGENTS.md §2 lists them: `/assistant/chat`, `/auth/logout`, `/products/{id}/availability`, `bookingCode`.

### - [ ] 23. `/search` is far over its latency budget on the cloud

- NFR-PERF-01: spec §7.1 measured p95 4.0 s on 01/10 (budget 300 ms). Weaviate Cloud is in another region (dense 1.8 s + BM25 2.1 s).
- The logged-in `/recommendations` path has never been measured on the cloud.

## Reported in history, not verified here (need VM/GCP access)

### - [ ] 24. Rotate the SSH and DB passwords pasted into a chat on 30/09

- Source: `history/2026-10-01-cloud-index-dong-bo-catalog-vm.md`.

### - [ ] 25. Primary VM SSH is open to `0.0.0.0/0`

- Brute-force attempts were seen. Restrict it to IAP `35.235.240.0/20`.
- Source: `history/2026-10-01-fix-replica-basebackup-mat-khau.md`.

### - [ ] 26. Monitor port 8765 is public without a login

- Source: `history/2026-09-30-monitor-tab-db.md`.

### - [ ] 27. JWT PEM keys and `/etc/vota/daily.env` are not managed by Secret Manager

- Source: `history/2026-10-02-inject-backend-env-from-secret-manager.md`.
