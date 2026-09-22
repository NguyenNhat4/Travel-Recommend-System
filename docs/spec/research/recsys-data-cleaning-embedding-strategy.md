# RecSys research: cleaning a noisy travel catalog, embedding it, and searching it

**Date:** 2026-09-20 · **Scope:** research only, no code · **Inputs read:** `recsys-internship-handbook-v3-vi.md`, everything in `docs/spec/`, `docs/spec/data-collection/schema.md`, `EXPAND_CATALOG.md`, `sample/products-sample.jsonl`, and the catalog audit of 2026-09-17.

This document answers three questions for the Search/Recommendation workstream:

1. What noise is actually in our catalog, and what does each kind do to an embedding index?
2. How should we build the text, choose the model, and index/search so that noise does not dominate results?
3. Which recommendation algorithm fits our data, and what (if anything) is worth training or fine-tuning?

Contract constraints that this research respects: filter → score → cutoff (`hop-dong-tich-hop-search-recommendation.md` §2.2), exact scan until 50k vectors (§2.4), two-tier catalog with only parents embedded (§2.1), `because[]` explanations (§4.6), and the handbook's ban on training a neural network from scratch (§2 "Ngoài phạm vi"). Fine-tuning an existing sentence-transformer is domain adaptation, not training from scratch; it is listed here as an optional ablation, and the team should confirm that reading with the mentor before spending time on it.

---

## 1. What the catalog really looks like

Numbers from `evidence/catalog-audit-2026-09-17.json` and `SCHEMA.md`.

| Fact | Value | Why it matters for embeddings |
|---|---|---|
| Rows in `products.jsonl` | 10,000 | Only ~1,125 are "parent" products worth a vector |
| Synthetic rows (`sourceRef` starts with `synthetic:`) | 7,784 | Generated from templates; they are near-duplicates of each other by construction |
| Real rows | 2,216 | The only text with real signal |
| Real descriptions that are *derived* (template-built from attributes) | 1,275 / 2,216 = 57.5% | 771 room descriptions are "room info + hotel description"; 244 flight descriptions are a fixed sentence pattern |
| Hotel rooms | 4,646 (907 real) | 907 real rooms map to 316 properties, ~2.9 rooms each; siblings share most text |
| Attractions | 3,517 (407 real) | 139 real ones are un-ticketed public POIs; description lengths up to 7,000+ chars |
| Flights | 184 child + 60 routes | Description contains the price and the date, which drift |
| Amenity lists | median 10, max 78 per product | Sample rooms carry 30–45 items, most of them generic ("Wifi miễn phí", "Dép đi trong phòng") |
| Star rating coverage | 51% | Cannot be a hard filter; contract already treats it as soft |
| Destination = "Nha Trang" style dominance | 20 destinations, heavily skewed | Destination name repeats in name, description, address, venue |

Observed in the 50-row sample:

- Room descriptions are 150–350 characters of generic prose ("được thiết kế hiện đại, tích hợp đầy đủ tiện nghi…"); the only distinguishing facts are size, bedrooms, view, capacity, and 2–5 distinctive amenities (private pool, kitchenette, family room).
- Flight descriptions are one templated sentence: airline, code, airports, times, duration, "Giá một chiều từ 663.000₫ (ngày 2026-09-25)".
- Attraction descriptions from vinpearl.com are long marketing pages with headings, promo codes ("Nhập mã HELLO5 giảm 5%"), and sub-venue opening hours.
- The same real-world entity appears under several rows and taxonomies: "VinWonders Nha Trang" is an attraction ticket, a trip.com POI (`poiRef`, `sameAs`), the `venue` of several tickets, and a component of combos.
- Property descriptions derived from booking.com read as "X là cơ sở lưu trú 5 sao tại Đà Nẵng. Địa chỉ: … Tiện ích: … Điểm đánh giá 8.6/10".

---

## 2. Noise taxonomy and what to do about each

Each item lists: the symptom, what it does to cosine search, and the fix. Fixes are ordered cheapest first.

### N1. Sibling near-duplicates (rooms of one hotel, flights of one route)

- **Effect:** a query for "resort biển cho gia đình" returns five room types of one resort; `/similar` for a room returns its siblings. This is the classic "averaging returns more of the same" failure.
- **Fix (already in contract C5):** embed only parents. Rooms and flights are variants, not documents. Keep a *small* separate room-vector table only if the product page needs "rooms like this one" inside a hotel.
- **Extra:** if rooms must be searchable ("biệt thự 3 phòng ngủ hồ bơi riêng"), embed the **room delta text only** (room name, size, bedrooms, bed, view, capacity, 3–5 distinctive amenities) and attach `parentProductId` for collapsing. Do not paste the hotel description into the room text; that is exactly what the derived descriptions did, and it is why 771 rooms look alike.

### N2. Amenity boilerplate

- **Effect:** 30–45 amenities per room, most shared by nearly every product in the same taxonomy. When they go into the embedded text, every hotel drifts toward the same "generic hotel" point and hubness appears (a few products show up in every top-k). Research on anisotropic embedding spaces describes exactly this: documents near the centroid become nearest neighbours to everything.
- **Fix:**
  1. Build a **canonical amenity vocabulary** (the way Booking.com groups its HAC/RMA amenity codes: "Desk", "Desk with lamp", "Large desk" collapse into one code). Map the ~78 observed strings to ~40 canonical codes with a hand-written synonym table; keep the code list in `config.yaml`, not in code.
  2. Compute **document frequency per taxonomy**. Amenities present in more than ~60% of products of the same taxonomy (Wifi, TV, điều hoà, dép, máy sấy tóc, lễ tân 24h) are **excluded from the embedding text** and kept only as structured attributes. Amenities with low frequency (hồ bơi riêng, bếp nhỏ, câu lạc bộ trẻ em, bãi biển riêng, spa, sân golf) stay in the text because they are what a query actually asks for.
  3. Cap the number of amenities in text at ~8, ordered by rarity.

### N3. Template-derived descriptions (`descriptionSource` is set)

- **Effect:** 57.5% of real descriptions are built from attributes. They add no information beyond the attributes, and the same template words appear thousands of times, so they pull all products of that template toward one point.
- **Fix:** for any product with `descriptionSource`, **do not embed the derived paragraph**. Rebuild the passage from attributes with the text builder in §3, which controls wording and length. Only original source text (vinpearl.com prose, `descriptionOriginal` when it is Vietnamese) goes in verbatim. Record `quality_tier` (`original` / `derived` / `synthetic`) on every vector row so evaluation can slice by it.

### N4. Destination dominance ("200 products in Nha Trang")

- **Effect:** the destination name appears in the product name, description, address, venue, and province. Embeddings then cluster by destination first and by product type second, so "resort cho gia đình" returns Nha Trang everything, and two different Nha Trang products look more similar than two family resorts in different cities.
- **Fix:**
  1. Destination is a **hard filter** (contract §2.5). Search and recommendations should never rely on the vector to "know" the destination.
  2. In the embedded text, mention the destination **exactly once**, in a fixed position (e.g. "Điểm đến: Nha Trang."). Strip repeated occurrences from the description, and never embed `address`, `province`, `venue` strings when they only repeat the city.
  3. Measure "destination leakage": for a query with no destination and no filter, what fraction of the top-10 share one destination? This should be close to the catalog share, not 100%.

### N5. Long marketing pages (attractions up to 7,000+ chars)

- **Effect:** `multilingual-e5-base` truncates at 512 tokens, so only the intro is embedded; the rest (water park, safari, opening hours) is invisible to search. `bge-m3` accepts 8,192 tokens but a single vector for a long page still averages everything into mush.
- **Fix:** split long descriptions into ~200–300 token passages (by heading, then by sentence), embed each passage, and score a product as **max over its passages** (MaxP) for `/search`. For the user-profile vector, use the **mean** of passages (or just the first passage) so one product contributes one vector. Store passages in a `product_passages` table keyed by product; the contract does not need to change because results are still per product.

### N6. Promo codes, prices, dates, and policies inside description text

- **Effect:** "Nhập mã HELLO5", "Giá một chiều từ 663.000₫ (ngày 2026-09-25)", opening-hour lists, cancellation policies. They add tokens that carry no product meaning and go stale.
- **Fix:** regex strip promo codes, prices with currency symbols, ISO dates, phone numbers, URLs, and "Tại sao nên đến…"-style headings before embedding. `policies` is already separated in attributes; keep it out. Opening hours belong to the itinerary agent, not the vector.

### N7. Mixed language and unaccented text

- **Effect:** room names are English ("Deluxe Ocean View", "Studio", "Junior Suite"); queries are Vietnamese; users often type without diacritics ("nghi duong bien cho gia dinh"). Multilingual models handle Vietnamese↔English reasonably, but unaccented Vietnamese is tokenised as different pieces and degrades sharply.
- **Fix:** the text builder adds a Vietnamese gloss for known room-type tokens (Ocean View → hướng biển, Suite → phòng suite, Villa → biệt thự, Bungalow → bungalow). For queries: detect "no diacritics" (ratio of Vietnamese-marked characters ≈ 0) and run the lexical leg on an `unaccent`ed index; for the dense leg, an LLM or a small dictionary restores diacritics for the ~50 most common travel words. Also keep 5 unaccented queries in the negative/weak test set.

### N8. Same entity under many rows and taxonomies

- **Effect:** VinWonders Nha Trang (ticket), VinWonders Nha Trang (POI), Combo Vinpearl + VinWonders, and tickets whose `venue` is VinWonders all score high together. Cross-source hotel duplicates (vinpearl / booking / agoda) were already merged (53 pairs), but POI-level duplication across taxonomies is not.
- **Fix:** an **entity layer**: `poiRef` / `sameAs` / `venue` resolve to one `entity_id`. Search collapses to at most 2 results per `entity_id` the same way it collapses per `parentProductId`. Combos reference component entities instead of duplicating their text.

### N9. Synthetic rows (7,784) are template clones

- **Effect:** if all 10,000 rows are embedded, any query returns synthetic clones first, because there are 3–7 of them per destination per type and they are mutually near-identical. Real Vinpearl products, the ones stakeholders recognise, get pushed down.
- **Fix:**
  1. **Near-duplicate detection before indexing.** Exact hash on normalised text, then MinHash/LSH on 5-gram shingles (Jaccard ≥ 0.8 = duplicate candidate), then embedding cosine ≥ 0.95 within the same destination block. Cluster, pick one canonical row per cluster by `quality_score`, and store the rest as `product_sources` variants. This is the standard two-stage recipe (MinHash for surface duplicates, embedding for paraphrases).
  2. Add a **`quality_tier` boost** in the final score (original > derived > synthetic) so that ties break toward real products.
  3. For the demo, consider indexing synthetic products only for destinations where real coverage is missing.

### N10. Attributes that are absent, false, or inferred

- `starRating` 51% coverage, `familyFriendly` inferred from names, booleans stored as `false` vs absent. Absent ≠ false (contract C2). Only put an attribute into text when it is present and truthy; never emit "không có hồ bơi" for a missing key.

### N11. Brand and code tokens that embeddings mangle

- "VinWonders", "VinHolidays Fiesta", "Meliá Vinpearl", "VJ1582", "Grand World". Dense models smear rare proper nouns into their neighbourhood; the handbook already notes this for VinWonders. **Fix:** a lexical leg (§5.3) and RRF fusion. The handbook schedules hybrid search for Week 5 and lists it as the third thing to cut; this research recommends pulling a *minimal* lexical leg (name + brand + venue only, via `pg_trgm`/`unaccent`) into Week 2 because brand queries are core to the demo.

### N12. Flights are not a semantic-search problem

- The only meaningful flight query is structured: origin, destination, date, time band, airline. Embed **routes only** ("Vé máy bay Hà Nội – Cam Ranh, bay thẳng, 1 giờ 50 phút, VietJet/Vietnam Airlines") and serve child flights by structured filter and sort. Do not put prices or dates in the route text.

### N13. Non-bookable rows

- `ticketed=false` POIs with 0 VND, parent properties, and routes are not bookable. They can appear in search and itineraries, but `/recommendations` must exclude them (contract R07). Keep a `bookable` boolean on the vector row so the filter is one predicate.

### N14. Capacity and party-size queries

- "cho 6 người", "gia đình 2 con nhỏ" are structured needs (`maxOccupancy`, `familyFriendly`, `bedrooms`). The vector will not count people. **Fix:** a small query-understanding step extracts numbers and party words into filters before the vector search. The itinerary agent already does intent extraction; `/search` can reuse the same extractor for the web UI.

---

## 3. Text builder: one template per taxonomy

The handbook says the text builder matters more than the model choice. The rules that came out of the noise analysis:

**Global rules**

- One passage per parent product, target 120–250 tokens, hard cap ~400 tokens. Long originals are chunked (N5).
- Field order is fixed: `name` → type phrase → destination once → distinctive facts → distinctive amenities → audience → short original prose.
- Prefix `passage: ` for e5-family models; queries get `query: ` (required by the model card; without prefixes e5 quality drops).
- Never include: address, province, URLs, prices, dates, promo codes, policies, opening hours, generic amenities, `descriptionSource` paragraphs, review counts (they go into the score, not the text).
- Vietnamese only, NFC-normalised, diacritics kept; English room-type words get a Vietnamese gloss.

**Templates**

| Taxonomy | Passage skeleton |
|---|---|
| `hotel/property` | `{name}. {propertyType or "Khu nghỉ dưỡng"/"Khách sạn"} {starRating} sao tại {destination}. {beachfront/riverside/city-centre phrase if known}. Nổi bật: {≤8 rare amenities}. Phù hợp: {audience/familyFriendly}. {first 2–3 sentences of original description, stripped}` |
| `hotel/room` (only if room search is needed) | `{roomName} tại {hotelName}. Diện tích {m²}, {bedrooms} phòng ngủ, {bed}, tối đa {maxOccupancy} khách, {view}. Nổi bật: {≤5 rare amenities}.` No hotel prose. |
| `attraction` (ticketed) | `{name}, {tags e.g. công viên giải trí / safari / bảo tàng} tại {destination}. Dành cho: {audience}. Thời lượng gợi ý {durationMinutes → giờ/ngày}. {top 3 sub-areas or highlights}. {2–3 original sentences}` |
| `attraction` (POI, un-ticketed) | Same, plus "điểm tham quan công cộng" so the itinerary agent can tell it apart. |
| `combo` | `{name}: combo gồm {component names joined}. {nights} đêm tại {hotel entity}, kèm {ticket entities}. Phù hợp: {audience}.` Components are references, not copied prose. |
| `golf` | `{courseName} tại {destination}: sân golf {holes} lỗ, par {par}, {view/links/resort style}, {caddie/buggy included}.` |
| `flight/route` | `Vé máy bay {originCity} – {destinationCity} ({originAirport} – {destinationAirport}), bay thẳng, khoảng {duration}. Hãng: {airlines seen}.` |

**Why this is the biggest lever:** it removes N2, N3, N4, N6 and most of N9 at the source. Handbook §11 Week 2 assigns this to the Data workstream; the Search workstream should review it against the 80 labelled queries.

---

## 4. Deduplication pipeline (product level and entity level)

Two different problems, two pipelines:

| Level | Problem | Method | Already specified? |
|---|---|---|---|
| Entity (same hotel on 3 sites) | Different names/prices for one physical place | Block by destination → geo < 150 m **or** trigram(name) ≥ 0.82 with star diff ≤ 1 → field-wise winner rules | Yes, `data-collection-spec.md` §7 |
| POI (same venue across taxonomies) | Ticket, POI, venue, combo component | Resolve `poiRef`, `sameAs`, `venue` to `entity_id`; collapse in results | No, proposed in N8 |
| Text (near-identical passages) | Synthetic clones, derived templates | Exact hash → MinHash/LSH 5-gram shingles (Jaccard ≥ 0.8) → cosine ≥ 0.95 in same destination → cluster, keep canonical by `quality_score` | No, proposed in N9 |

Write the outcome into a `dedup_review.csv` for the grey zone (Jaccard 0.6–0.8 or cosine 0.90–0.95) the same way the entity dedup spec does. Expect the text-level pass to shrink the embedded set from ~5,000 parents (with synthetic) to something much closer to the ~1,100 real parents plus a controlled number of synthetic canonicals.

---

## 5. Embedding, indexing, and search strategy

### 5.1 Model shortlist and how to decide

| Model | Dim | Context | Notes from research |
|---|---|---|---|
| `intfloat/multilingual-e5-base` (handbook default) | 768 | 512 | Strong multilingual retrieval; needs `query:`/`passage:` prefixes; cosine range compressed to ~0.7–1.0 because of the 0.01 InfoNCE temperature, so absolute thresholds are fragile (the contract's margin rule exists for this reason). |
| `BAAI/bge-m3` | 1024 | 8192 | Best quality of the three in the handbook; one model gives dense + **sparse lexical weights** + ColBERT vectors. The sparse output is a free lexical leg for brand names (N11). Heaviest; measure CPU latency against the 60 ms embed budget. |
| `paraphrase-multilingual-MiniLM-L12-v2` | 384 | 128 | Fast, but 128-token context and weaker retrieval; only viable if latency forces it. |
| `AITeamVN/Vietnamese_Embedding` | 1024 | 8192 | bge-m3 fine-tuned on ~300k Vietnamese triplets; reported to beat bge-m3 and `vietnamese-bi-encoder` on Vietnamese retrieval. Strong candidate to add to the Week 2 comparison. |
| `bkai-foundation-models/vietnamese-bi-encoder` | 768 | 256 | PhoBERT-based, requires **word segmentation** (pyvi/underthesea) before encoding; Vietnamese-only, so English room names may suffer. Good on Vietnamese legal/QA benchmarks. |

Decision protocol (Week 2, Evaluation workstream):

1. Same text builder output for all models.
2. 80 labelled Vietnamese `query → productId` pairs + 10 negative queries + 5 unaccented queries + 10 brand queries (VinWonders, Meliá, Grand World…).
3. Metrics: Recall@5/10, MRR@10, weak-detection rate on negatives, **sibling collapse rate** (share of top-10 that share a parent/entity), **destination leakage** (N4), **hub rate** (k-occurrence: how often each product appears across all top-10 lists; anything in more than ~20% of lists is a hub and its text needs inspection).
4. p95 embed latency on the deployment CPU.
5. Lock the model and dimension; the dimension is in the schema and changing it later is a full reindex.

Do not truncate e5 vectors to save space: e5-base was not trained with Matryoshka loss, so prefix truncation is not safe. At ≤ 10k vectors, 768 or 1024 dims in `shared_buffers` is a few MB; size is not a problem.

### 5.2 Index layout

- `product_vectors`: one row per **canonical parent** (property, route, attraction, combo, golf), `quality_tier`, `bookable`, `entity_id`, `parent_product_id`, plus the hard-filter columns copied in (`taxonomy`, `destination`, `unit_price`, `available`) so the filter-first query touches one table.
- `product_passages` (optional, for N5): several rows per long product, MaxP at query time.
- Optional `product_room_vectors` for room-level `/similar` inside a hotel (N1).
- Exact scan with `WHERE` filters first (contract §2.2/§2.4). If the catalog ever grows past 50k, switch to HNSW with `hnsw.iterative_scan = relaxed_order` and a partial index per taxonomy; pgvector's own docs warn that with the default `ef_search = 40` a 10% selective filter yields ~4 rows, which is exactly the category-exclusion case in `/recommendations`.

### 5.3 Hybrid search (lexical leg)

Postgres has no Vietnamese text-search configuration. Two workable options at our scale:

1. **`simple` config + `unaccent` on syllables** for `name`, `brand`, `venue`, `hotelName`, plus `pg_trgm` similarity for misspellings. No word segmentation needed for a 10k catalog; syllable matching plus trigrams is enough for brand and place names. (Segmenters exist: underthesea ≈ 80% segmentation accuracy in one public benchmark vs pyvi ≈ 58%, but they add a dependency for little gain here.)
2. **bge-m3 sparse weights** stored as a sparse vector, if bge-m3 is the chosen dense model.

Fuse with **Reciprocal Rank Fusion** (`1/(60 + rank)`), which avoids normalising incomparable scores. Apply the same cutoff logic to the dense leg only, and treat a lexical-only hit as a match when it is an exact name/brand match.

### 5.4 Reranking

`BAAI/bge-reranker-v2-m3` (multilingual cross-encoder) on the top 30–50 dense+lexical candidates improves precision for nuanced Vietnamese queries. Reported latency is 80–200 ms per 100 docs on a small GPU; on CPU it will likely break the 300 ms p95 budget, so treat it as an ablation behind a flag, not a default. A cheaper "rerank" is structured boosting: `+γ·log(1+reviewCount)` (already in contract §4.7), `+quality_tier`, `+bookable`.

### 5.5 Hub control

After indexing, run the 90 evaluation queries plus ~200 LLM-generated queries, count k-occurrence per product, and inspect the top hubs. In practice hubs are products whose passage is all boilerplate; the fix is the text builder, not a ranking hack. Re-check after every text builder change.

### 5.6 Score calibration and cutoff

Because e5 scores live in 0.7–1.0, calibrate `search.cutoff` (provisional 0.62) on the labelled set; expect the real value to land near 0.78–0.82 for e5 and lower for bge-m3. Keep the contract's margin rule (`topScore − median(F)`) since it is robust to the compressed range. Report `backgroundScore` from the same exact scan.

---

## 6. Recommendation algorithm: what fits our data

**Content-based user vectors (handbook §1, contract §4.3) are the right choice**, and the research backs the reasoning:

- Interaction data is 500 seeded profiles with 1,500–2,500 events, most users with 1–5 events per year. Collaborative filtering, two-tower models, and item2vec need orders of magnitude more; Airbnb trained its 2018 listing embeddings on 800M click sessions and still needed a special cold-start rule (average of the 3 nearest listings of the same type and price band). With synthetic sessions, a learned item2vec would only learn the generator.
- What Airbnb's paper *does* transfer to us: (a) the booked item as global context that dominates the session, which is our `w(purchase)=5`; (b) market-aware negatives, which becomes "same-destination, same-taxonomy siblings are the hard negatives" in §7; (c) explicit negative signals (skipped/dismissed items), which map to the V2 `recommendation_dismissed` event.

Cheap additions that improve `/recommendations` without new models:

1. **Cross-vertical transition prior.** From seeded trips, estimate P(next taxonomy | taxonomies booked so far, destination). Use it to pick `nextVertical` and then run the vector search *inside* that taxonomy. This is more defensible than "exclude booked taxonomies and hope" and it feeds `diagnostics.excludedVerticals`.
2. **Entity-aware exclusion.** Exclude the *entity* the user booked (hotel and its rooms, venue and its tickets), not just the `productId`.
3. **Popularity prior + MMR** (contract §4.7) with the 2-per-parent cap extended to 2-per-entity.
4. **Cold start** stays rule-based (popular in destination → popular from home city → global popular, max 2 per taxonomy).
5. **Dormant** users: half-life × 3 and `lastDestination` boost, as in the contract.

Booking.com's KDD 2019 lessons apply directly: offline metric gains do not equal business value, and about 30% extra latency cost them ~0.5% conversion, so the 300 ms budget should win over model sophistication.

---

## 7. Training or fine-tuning: options ranked by cost and benefit

| Level | What | Data needed | Cost | Expected effect | Recommendation |
|---|---|---|---|---|---|
| 0 | No training: text builder + canonical amenities + dedup + hybrid | none | days of data work | Largest gain of all levels; fixes N1–N9 at the source | **Do this, Weeks 1–3** |
| 1 | Fine-tune the chosen bi-encoder with **LLM-generated Vietnamese queries** (Promptagator/InPars style) + `MultipleNegativesRankingLoss` + **mined hard negatives** | 5–10k (query, product) pairs from real/derived passages; hold out the 80 human pairs as the only test set | 1 GPU-hour on Colab; a few days of pipeline work | Published domain-adaptation gains are ~6 NDCG points (GPL) and a Vietnamese legal-retrieval study reports strong gains from synthetic queries + hard negatives | Optional ablation in Week 5 or "next six weeks" proposal; confirm scope with mentor |
| 2 | GPL (query generation + cross-encoder pseudo-labels + MarginMSE) | same corpus | similar to Level 1 | Comparable; the default T5 query generator is English-centric, so use an LLM for Vietnamese queries and `bge-reranker-v2-m3` as the labeller | Only if Level 1 underperforms |
| 3 | Add `MatryoshkaLoss` during Level 1 so 256-d truncation is safe | same | free on top of Level 1 | Smaller index; irrelevant at 10k vectors | Skip |
| 4 | Two-tower / item2vec on interactions | real CDP events at scale | high | Airbnb-class results need real sessions | Future work when production CDP access exists |

Design details for Level 1, if approved:

- **Query generation:** prompt the LLM with the *structured attributes and original prose*, ask for 1–5 queries per product covering different aspects (family, view, budget, activity), in Vietnamese, some without diacritics, some in English. Reject queries that just paraphrase the product name.
- **Consistency filter:** keep a query only if the base model retrieves its source product in its top-k (round-trip filter). This is the standard quality gate and removes hallucinated queries.
- **Hard negatives:** sample from the same destination and taxonomy (siblings, neighbours). This directly teaches the model to separate "Nha Trang family resort" from "Nha Trang business hotel", which is the failure mode in N4. Use `sentence_transformers.util.mine_hard_negatives` and `InformationRetrievalEvaluator`.
- **Leakage guard:** never generate training queries from synthetic rows (the model would learn the generator's template), and never train on the 80 labelled pairs.
- **Risk:** fine-tuning shifts the score distribution, so `cutoff` and `WEAK_RESULT_*` must be recalibrated and `embedding_version` bumped (contract §7.4).

---

## 8. Evaluation plan tied to the noise

Search (Week 2, repeat after every text-builder change):

- Recall@5/10, MRR@10 on the 80 labelled pairs; weak-rate on 10 negatives; 5 unaccented and 10 brand queries as separate slices.
- Sibling collapse rate, destination leakage, hub rate (definitions in §5.1).
- Slice every metric by `quality_tier` (original / derived / synthetic) to prove the demo runs on real products.

Recommendations (Week 3–5):

- The handbook's protocol is "hide each user's last booking". Recent RecSys work shows pure leave-one-out lets training and test periods overlap and can flip model rankings. Cheap fix: pick a **global date boundary**, use only bookings after it as test targets, and train user vectors from events before each target. Report both protocols if time allows.
- Baselines: random, most-popular, most-popular-in-destination (must beat the third).
- Cross-category rate, availability precision (exclude non-bookable), catalog coverage, p95 latency.
- Ablations (two variables max if time is short): text builder with vs without boilerplate removal; dense-only vs hybrid.

---

## 9. Where this lands in the six-week plan

| Week | Add to the existing plan |
|---|---|
| 1 | Canonical amenity vocabulary + document-frequency table; `quality_tier`; entity resolution for POIs; text-level dedup pass over synthetic rows |
| 2 | Text builder per taxonomy (§3); chunking for long attractions; model comparison with the extra metrics (§5.1); minimal lexical leg for names/brands |
| 3 | Cross-vertical transition prior; entity-aware exclusion; hub check |
| 4 | Query understanding shared with the itinerary agent (party size, budget, no-diacritics) |
| 5 | Full RRF hybrid; optional cross-encoder rerank behind a flag; optional Level 1 fine-tune as an ablation; recalibrate cutoff |
| 6 | Report: noise taxonomy, before/after metrics by `quality_tier`, "next six weeks" including Level 4 when real events exist |

---

## 10. Sources consulted

Project documents: handbook v3; `data-collection-spec.md`; `hop-dong-tich-hop-search-recommendation.md`; `hop-dong-tich-hop-itinerary-assistant.md`; `ra-soat-hop-dong-2026-09-17.md`; `schema-database-toan-bo-v2.md`; `docs/spec/data-collection/schema.md`, `EXPAND_CATALOG.md`; `evidence/catalog-audit-2026-09-17.json`; `sample/products-sample.jsonl`.

Deduplication
- [Finding near-duplicates with Jaccard similarity and MinHash](https://blog.nelhage.com/post/fuzzy-dedup/)
- [Deduplication: exact and near-duplicate removal (ZeroEntropy)](https://zeroentropy.dev/concepts/deduplication/)
- [SemHash semantic deduplication](https://medium.com/@sreeprad99/how-semhash-simplifies-semantic-deduplication-for-llm-data-a0b1a53e84fe)
- [FOLD: fuzzy online deduplication via ANN](https://arxiv.org/html/2606.03001v1)

Hotel data normalisation
- [Booking.com Hotel Amenity Codes (OTA HAC)](https://developers.booking.com/connectivity/docs/codes-hac) · [Room Amenity Type Codes (RMA)](https://developers.booking.com/connectivity/docs/codes-rma)
- [Why most OTAs still get hotel mapping wrong (Vervotech)](https://vervotech.com/blog/why-most-otas-still-get-hotel-mapping-wrong/)
- [Hotel mapping tools overview (AltexSoft)](https://www.altexsoft.com/blog/hotel-mapping-tools-how-giata-gimmonix-databindr-and-other-solutions-work/)

Embedding models and Vietnamese
- [multilingual-e5-base model card](https://huggingface.co/intfloat/multilingual-e5-base) · [Discussion: cosine range 0.7–1.0](https://huggingface.co/intfloat/multilingual-e5-large/discussions/10) · [Multilingual E5 technical report](https://arxiv.org/pdf/2402.05672)
- [BGE-M3 model card](https://huggingface.co/BAAI/bge-m3) · [BGE-M3 paper](https://arxiv.org/html/2402.03216v3) · [Hybrid dense+sparse+ColBERT with BGE-M3](https://yuniko.software/bge-m3-qdrant/)
- [bkai-foundation-models/vietnamese-bi-encoder](https://huggingface.co/bkai-foundation-models/vietnamese-bi-encoder)
- [Vietnamese_Embedding (bge-m3 fine-tuned on Vietnamese triplets)](https://www.promptlayer.com/models/vietnameseembedding/)
- [Advancing Vietnamese Information Retrieval with Learning Objective and Benchmark](https://arxiv.org/html/2503.07470v1)
- [Improving Vietnamese Legal Document Retrieval using Synthetic Data](https://arxiv.org/abs/2412.00657)
- [MMTEB benchmark](https://arxiv.org/html/2502.13595v1)

Text construction, long documents, multi-field
- [Semantic Product Search for Matching Structured Product Catalogs](https://arxiv.org/pdf/2008.08180)
- [Multi-Field Adaptive Retrieval](https://arxiv.org/html/2410.20056) · [Multi-Aspect Dense Retrieval (Google)](https://research.google/pubs/multi-aspect-dense-retrieval/)
- [Lost in a Single Vector: chunk evidence aggregation for long documents](https://arxiv.org/pdf/2606.18781) · [Rethinking chunk size for long-document retrieval](https://arxiv.org/html/2505.21700v2) · [Late Chunking](https://arxiv.org/pdf/2409.04701)

Hubness
- [When Global Gating Is Enough: admission-time hubness control](https://arxiv.org/abs/2606.19692)
- [Anisotropy in embedding representations](https://www.emergentmind.com/topics/anisotropy-in-embedding-representations)

Hybrid search, Postgres, pgvector
- [Hybrid search in PostgreSQL: BM25, sparse vectors, RRF (pgEdge)](https://www.pgedge.com/blog/hybrid-search-in-postgresql-bm25-sparse-vectors-and-reciprocal-rank-fusion)
- [Hybrid Search in PostgreSQL: the missing manual (ParadeDB)](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [pgvector filtering docs (iterative scan, partial indexes)](https://docs.pgedge.com/pgvector/v0-8-1/filtering/) · [Tuning pgvector (ParadeDB)](https://www.paradedb.com/learn/postgresql/tuning-pgvector)
- [PostgreSQL unaccent](https://www.postgresql.org/docs/current/unaccent.html) · [Vietnamese tokenizer benchmark](https://huybik.github.io/Word-Tokenizer-Benchmark/)

Reranking
- [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) · [Best rerankers 2026 comparison](https://futureagi.com/blog/best-rerankers-for-rag-2026/)

Fine-tuning and synthetic queries
- [Sentence-Transformers training overview](https://sbert.net/docs/sentence_transformer/training_overview.html) · [Domain adaptation (TSDAE, GPL)](https://sbert.net/examples/domain_adaptation/README.html) · [Matryoshka embeddings](https://sbert.net/examples/sentence_transformer/training/matryoshka/README.html)
- [GPL paper](https://arxiv.org/pdf/2112.07577) · [GPL walkthrough (Pinecone)](https://www.pinecone.io/learn/series/nlp/gpl/) · [MNR loss (Pinecone)](https://www.pinecone.io/learn/series/nlp/fine-tune-sentence-transformers-mnr/)
- [Study on LLMs for Promptagator-style dense retriever training](https://arxiv.org/html/2510.02241) · [InPars toolkit](https://arxiv.org/pdf/2307.04601)
- [Airbnb: LLM-powered synthetic data for cold-start natural language search (2026)](https://arxiv.org/pdf/2605.21812)

Recommendation algorithms
- [Airbnb KDD 2018: Real-time personalization using embeddings](https://dl.acm.org/doi/10.1145/3219819.3219885) · [Explainer part 1](https://joseparreogarcia.substack.com/p/airbnb-listing-embeddings-part-1) · [part 2](https://joseparreogarcia.substack.com/p/airbnb-listing-embeddings-part-2)
- [Embedding-based retrieval for Airbnb search (two-tower)](https://medium.com/airbnb-engineering/embedding-based-retrieval-for-airbnb-search-aabebfc85839)
- [Two-tower models deep dive (Shaped)](https://www.shaped.ai/blog/the-two-tower-model-for-recommendation-systems-a-deep-dive)
- [150 successful ML models: 6 lessons at Booking.com (summary)](https://blog.acolyer.org/2019/10/07/150-successful-machine-learning-models/)

Evaluation
- [Time to Split: data splitting strategies for sequential recommenders (RecSys 2025)](https://arxiv.org/abs/2507.16289)
- [Data leakage in offline evaluation of sequential recommenders](https://dl.acm.org/doi/10.1145/3705328.3759329)
