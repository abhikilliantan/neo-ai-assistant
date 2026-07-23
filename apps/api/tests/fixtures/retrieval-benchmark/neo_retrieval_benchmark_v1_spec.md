# Neo Retrieval Benchmark v1

Permanent regression dataset for document retrieval. Re-run **unchanged** after any change to: chunk size, overlap, chunking algorithm, parser, embedding model, similarity floor, `top_k`, or reranking.

**Document:** `neo_retrieval_benchmark_v1.txt` (~2,900 words, 11 sections)

The document is designed adversarially. The word "days" appears in at least six unrelated contexts (annual leave, sick leave, compassionate leave, carry-over deadline, remote work, equipment return, expense deadline). Numeric and lexical overlap alone will not select the right passage — the retrieval has to distinguish topics.

## Method

1. Upload the document. Record the chunk count.
2. Run each query below **exactly as written**.
3. For each: record the match percentage, the citation char range, and whether the returned passage actually contains the expected answer.
4. Record configuration at time of run (chunk size, overlap, floor, `top_k`, embedding model).

Do not adjust any setting mid-run. A benchmark is only comparable if the whole set runs under one configuration.

## Queries

| # | Query | Expected answer | Lives in | Tests |
|---|-------|-----------------|----------|-------|
| 1 | `annual leave` | 26 days per calendar year | §3 | Direct lexical + numeric. Baseline. |
| 2 | `what computer will I be given` | MacBook Pro 16-inch (Engineering) / Dell Latitude 7450 (other) | §5 | Semantic — query shares no words with the passage. |
| 3 | `how much time off after a family bereavement` | 5 days at full pay | §3 | Disambiguation — competes with five other "days" figures. |
| 4 | `can I work from abroad` | Advance approval from People Ops + Finance; 30 consecutive days max | §2 | Policy nuance, not a keyword lookup. |
| 5 | `who do you call if something happens to me at work` | Emergency contact record; People Ops only | §10 | Conversational phrasing, distant section. |
| 6 | `what is the company dental insurance policy` | **NOTHING — no answer exists** | — | **Negative control.** |
| 7 | `where can I park my car at the office` | **NOTHING — no answer exists** | — | **Negative control** (facilities — no parking policy anywhere in the handbook). |
| 8 | `does the company pay for a gym membership` | **NOTHING — no answer exists** | — | **Negative control** (benefits — no gym/fitness/wellness perk; sits near the EAP §10 and learning-budget §8 without answering). |
| 9 | `how many paid days off do I get for jury duty` | **NOTHING — no answer exists** | — | **Negative control, adversarial** (leave — no jury-duty leave; competes directly with §3, which is full of "days"/"leave" and five real leave types). |

### The negative controls are the most important queries

The document contains no dental, parking, gym, or jury-duty policy. Correct behaviour for Q6–Q9 is **zero results** — the floor rejects everything. If any of them returns a passage, the floor is too permissive and every *positive* result becomes suspect, because we'd have no evidence the system can say "I don't know."

A benchmark that only tests recall will happily approve a system that matches everything.

**Why four, not one (added for the floor-lowering slice).** A single negative control (Q6 alone) proves too little: the safe floor window for voyage-3.5 on this corpus is only ~0.04 wide (real matches bottom out ~0.506; Q6's best-rejected candidate is ~0.457–0.462). One lucky control passing doesn't tell us how many genuinely-absent, plausible-sounding questions would sneak through at 0.46–0.48. Q7–Q9 were chosen to (a) be genuinely absent (verified against the corpus — unlike share-option vesting, which IS in §4/§11 and cannot be a negative), (b) sound like they belong in an employee handbook, and (c) span different sections so they probe different regions of the embedding space. Q9 (jury duty) is deliberately the hardest: it is leave-adjacent, so it stress-tests whether a lowered floor leaks a leave chunk as a confidently-wrong answer. **Lowering the floor ships only if ALL FOUR hold at zero.** A leak on any is the signal that no floor can separate signal from noise on this model, and that reranking (retrieve wide → calibrated rerank score → threshold on that) is the durable fix instead.

## Scoring

- **Pass:** returned passage contains the expected answer, cited range covers it, score above floor.
- **Partial:** correct passage but the cited range is far wider than the answer (imprecise citation).
- **Fail:** wrong passage, or nothing returned for queries 1–5.
- **Query 6 passes only on zero results.**

## Results log

Append a block per run. Never edit an old block.

```
Run:        v1 baseline
Date:
Commit:
Config:     chunk_size=1000 chars, overlap=200, floor=0.50, top_k=5, voyage-3.5 (1024d)
Chunks:     ___

Q1 annual leave                 ___%  chars ______  pass/partial/fail
Q2 what computer                ___%  chars ______  pass/partial/fail
Q3 bereavement                  ___%  chars ______  pass/partial/fail
Q4 work from abroad             ___%  chars ______  pass/partial/fail
Q5 emergency                    ___%  chars ______  pass/partial/fail
Q6 dental (expect ZERO)         ___results         pass/fail

Notes:
```


<!-- Appended by baseline run — do not edit; append new runs below. -->
```
Run:        v1 baseline
Date:       2026-07-21
Commit:     24937e81090e978e28b7b9f2a9905df850c868e9
Config:     chunk_size=1000 chars, overlap=200, floor=0.50, top_k=5, voyage-3.5 (1024d)
            (read from live settings: embedding_provider=voyage, document_dimensions=1024;
             document_parser=mock, but .txt routes to the real TextDocumentParser via the
             8f-1 content-type dispatcher — confirmed 23 real chunks, not mock blocks)
Chunks:     23

Q1 annual leave                 66.6%  chars 3200-4200    partial
Q2 what computer                52.4%  chars 7200-8200    pass
Q3 bereavement                  51.2%  chars 4800-5800    partial
Q4 work from abroad             50.9%  chars 3200-4200    pass
Q5 emergency                    53.8%  chars 15200-16200  pass
Q6 dental (expect ZERO)         0 results                 pass

Passage heads (first ~100 chars of the top result):
Q1: "nt. Requests to work remotely from a country other than the country of employment must be approved in"
Q2: "bove the minimum.\n\n\nSECTION 5 - EQUIPMENT AND ASSETS\n\nEvery employee is issued a laptop appropriate"
Q3: "yee's country of employment, and the employee is referred to occupational health.\n\nParental leave fol"
Q4: "nt. Requests to work remotely from a country other than the country of employment must be approved in"
Q5: "d socialising. Managers should be aware that pressure to drink, however lightly meant, is a form of ex"
Q6: (no results)

Notes:
- Retrieval correctness: 6/6. Each Q1-Q5 expected answer was present in the top result
  above the 0.50 floor; Q6 (negative control) correctly returned ZERO results.
- Citation precision is coarse: chunks are fixed 1000-char windows, so every cited range
  is ~6-20x the length of the 1-2 sentence answer. Verdicts split PASS vs PARTIAL on
  whether the answer leads the chunk or is buried behind an unrelated section:
    * Q1 PARTIAL: chunk 3200-4200 contains "26 days per calendar year" (at char 3761) but
      OPENS in Section 2 remote-work; answer buried ~560 chars in - misleading lead-in
      despite the highest score (66.6%).
    * Q3 PARTIAL: correct "five days at full pay"/"bereavement" present in chunk 4800-5800
      (answer at char 5213) but only 51.2% (barely above floor), buried behind sick-leave/
      parental text - disambiguation only weakly succeeded.
    * Q2/Q4/Q5 PASS: the expected answer sits at/near the start of an on-topic chunk.
- Thin floor margin: real match scores span 50.4-66.6%. Q4 (0.5086) and Q3 (0.5118) clear
  the 0.50 floor by <0.02; a floor of ~0.52 would turn Q3/Q4 into FALSE NEGATIVES. The
  floor is well-placed today but has almost no headroom.
- Q2 (semantic, zero shared words with the passage) matched at 0.524 - cross-vocabulary
  retrieval works.
- The SAME chunk 3200-4200 is the top hit for BOTH Q1 and Q4: it straddles Section 2 ->
  Section 3 and holds both the work-from-abroad policy and the 26-days line. Good for Q4
  (answer leads), poor for Q1 (answer trails) - a direct artefact of fixed-size chunking
  ignoring paragraph/section boundaries.
- Only Q1 returned the full top_k=5; Q2-Q5 returned a single result each (the floor
  rejected ranks 2+). Q6 returned 0.
- Rate limiting: Voyage returned 429 during Q3 and Q6 (3 retries each, 25s waits, ~75s
  added per query). Scores/ranges are unaffected (embeddings are deterministic); only
  wall-clock timing was perturbed.
- Method: run via HTTP API (POST /api/v1/documents, POST /api/v1/documents/search) against
  the live dev stack on a freshly-registered, cleaned org; queries issued verbatim at the
  server-default top_k (no limit param). Real Voyage calls confirmed (200 OK to
  api.voyageai.com/v1/embeddings). No application code, settings, or .env were modified.
```


<!-- Appended by ADR 0001 block_aware run — do not edit; append new runs below. -->
```
Run:        v2 (ADR 0001 block_aware) — same corpus + queries as v1 baseline
Date:       2026-07-21
Commit:     working tree on 5617c07 + ADR 0001 impl (uncommitted); migration b7e3d9a1f2c4
Config:     chunk_size=1000 chars, overlap=200, floor=0.50, top_k=5, voyage-3.5 (1024d)
            document_chunker=block_aware (dev-only .env; default remains "fixed")
Chunks:     21   (v1: 23)

                                score   char range     runner-up   pass/partial/fail
Q1 annual leave                 65.6%   3730-4498      56.4%       pass
Q2 what computer                53.0%   7220-8172      <floor      pass
Q3 bereavement                  50.6%   5213-6323      <floor      partial
Q4 work from abroad             53.2%   2965-3761      <floor      pass
Q5 emergency                    54.4%   15313-16185    <floor      pass
Q6 dental (expect ZERO)         0 results  (best rejected 45.7%)   pass

Passage heads (first ~100 chars of the top result):
Q1: "SECTION 3 - LEAVE AND ABSENCE\n\nAnnual leave entitlement is 26 days per calendar year, in addition to"
Q2: "SECTION 5 - EQUIPMENT AND ASSETS\n\nEvery employee is issued a laptop appropriate to their role. Engin"
Q3: "Compassionate leave of up to five days at full pay is available following a bereavement. Extensions ar"
Q4: "Remote work is available to all employees whose role does not require physical presence. Employees att"
Q5: "SECTION 10 - HEALTH, SAFETY, AND EMERGENCY CONTACTS\n\nEvery employee must maintain a current emergency"
Q6: (no results; best below-floor candidate 45.7%)

ADR 0001 Open Question 2 acceptance gate (flip default only if ALL four hold):
  (a) Q1 top chunk begins with LEAVE content, not remote-work ......... PASS
      (v1 opened in Section 2 remote-work at char 3200; v2 opens in Section 3
       "Annual leave entitlement is 26 days..." at char 3730)
  (b) min margin above floor across Q1-Q5 >= 0.03 .................... FAIL
      v2 min = 0.006 (Q3, 0.5060-0.50); v1 min was 0.009 (Q4). WORSE, not better.
      (Q2 margin 0.0295 is also < 0.03.)
  (c) spread (highest Q1-Q5 - Q6 best-rejected) increases vs v1 ...... FAIL
      v1 = 0.6663 - 0.4622 = 0.2041 ; v2 = 0.6557 - 0.4574 = 0.1983. DECREASED.
  (d) Q6 still returns zero results .................................. PASS

RESULT: 2 of 4 criteria FAIL -> block_aware NOT accepted as default. Keep "fixed".

Notes:
- Citation QUALITY improved decisively (the ADR's stated target): chunk boundaries
  now land on paragraph/section edges. Q1 no longer opens mid-sentence in Section 2;
  Q1 (3730-4498) and Q4 (2965-3761) are now SEPARATE chunks (v1 shared 3200-4200).
  Q3/Q4/Q5 top chunks begin with the relevant section/answer.
- But retrieval DISCRIMINATION did not improve and slightly regressed on the gate
  metrics. Q3 dropped 0.5118 -> 0.5060: the block_aware bereavement chunk packs the
  compassionate + unpaid-leave paragraphs to ~1110 chars, so the averaged embedding
  is marginally less peaked on "bereavement" than v1's window. The compressed-score /
  thin-margin problem is a property of the embedding model + floor, NOT the chunker;
  block_aware does not move it.
- chunker provenance verified per-row: v2 rows carry chunker="block-aware-1",
  v1 rows "fixed-1" (backfilled). Recorded only; retrieval does not filter by it.
- Rate limiting: Voyage 429 during Q3 and Q6 (3 retries each, 25s waits). Scores/
  ranges unaffected (deterministic embeddings); wall-clock only.
- Method identical to v1: HTTP API, fresh org, clean corpus, six queries verbatim,
  no limit param (server-default top_k=5). "runner-up = <floor" means only one
  result cleared the 0.50 floor; the next candidate was below it (not returned).
- Recommendation: REVERT dev .env to document_chunker=fixed (done). Keep BlockAwareChunker
  in the tree behind config for the citation-quality win, but do not make it default:
  the OQ2 gate is not met. If the goal is citation precision rather than score margin,
  the gate itself may warrant revisiting — but per the accepted decision, this is a
  reject, and nothing was tuned to force a pass.
```


<!-- Appended by retrieval-recall slice (floor 0.50 -> 0.475 + 4 negative controls) — do not edit; append new runs below. -->
```
Run:        v3 (floor 0.475 + expanded negative controls Q7-Q9)
Date:       2026-07-23
Commit:     working tree (uncommitted): floor 0.50->0.475, spec adds Q7-Q9
Config:     chunk_size=1000 chars, overlap=200, floor=0.475, top_k=5, voyage-3.5 (1024d)
            document_chunker=block_aware (current code DEFAULT; ADR 0001 Amendment 1)
            (read from live settings: floor=0.475, model=voyage-3.5, chunker=block_aware, dim=1024)
Chunks:     21   (same corpus + block_aware as v2; deterministic ingest)
Method:     fresh registered org, doc uploaded via POST /api/v1/documents (real Voyage
            "document" embeddings). Per-query RAW similarity read from the exact
            production path (DocumentRepository.search_chunks, no floor) so both floors
            can be applied in analysis and negatives' best-rejected score is visible.
            Query embedded input_type="query". Voyage 429s retried (25s waits), not abandoned.

                                top raw   char range     verdict @0.475   margin vs 0.475
Q1 annual leave       [pos]     0.6557    3730-4498      PASS              +0.1807
Q2 what computer      [pos]     0.5295    7220-8172      PASS              +0.0545
Q3 bereavement        [pos]     0.5060    5213-6323      PASS              +0.0310  (worst positive)
Q4 work from abroad   [pos]     0.5317    2965-3761      PASS              +0.0567
Q5 emergency          [pos]     0.5436    15313-16185    PASS              +0.0686
Q6 dental      (ZERO) [neg]     0.4574    (best rejected)  ZERO RESULTS    -0.0176
Q7 parking     (ZERO) [neg]     0.4368    (best rejected)  ZERO RESULTS    -0.0382
Q8 gym         (ZERO) [neg]     0.4630    (best rejected)  ZERO RESULTS    -0.0120  (highest negative)
Q9 jury duty   (ZERO) [neg]     0.4410    (best rejected)  ZERO RESULTS    -0.0340

Ship criteria (BOTH must hold to ship the 0.475 floor):
  (a) Q1-Q5 return expected passages above 0.475, margins recorded ......... PASS
      (min margin 0.0310 at Q3 - clears the ADR 0001 >=0.03 bar, vs 0.006 at the old 0.50)
  (b) ALL FOUR negative controls return zero results ....................... PASS
      (highest negative = Q8 gym 0.4630, which is 0.0120 BELOW the 0.475 floor)

RESULT: SHIP the 0.475 floor. The safe window between worst true positive (Q3 0.5060)
and best true negative (Q8 gym 0.4630) is 0.0430 wide; 0.475 splits it, +0.031 below the
worst positive and +0.012 above the best negative.

Notes:
- Cross-validation: v3 positive scores match the v2 block_aware run almost exactly
  (Q1 65.57 vs 65.6, Q3 50.60 vs 50.6, Q6 45.74 vs 45.7) - embeddings are deterministic,
  same 21 block_aware chunks. The measurement path is sound.
- HONEST CAVEAT on what this proves. Every benchmark POSITIVE already cleared the OLD 0.50
  floor, so on THIS corpus 0.50 and 0.475 give the SAME pass/fail verdict. What v3 proves is
  the SAFETY question: the newly-admitted 0.475-0.50 band contains NO negative-control chunk
  (best negative 0.463 sits below it), so opening that band does not leak on four adversarial
  "sounds-like-it-belongs-but-absent" questions. The RECALL GAIN (real user NL phrasings that
  land at 0.46-0.50 and were being cut) is inferred from the score distribution, not directly
  demonstrated by these six clean queries - the benchmark has no positive in the 0.475-0.50 band.
- Q9 (jury duty) is the key adversarial win: leave-vocabulary, top-matched the §3 sick-leave
  chunk (4498-5411) as predicted, but at 0.441 - correctly BELOW floor. The leave-adjacent
  negative did NOT leak.
- Thin margin acknowledged: the safe window is only 0.043 wide and Q8 (gym) clears the floor by
  just 0.012 on the negative side. 0.475 is safe on this corpus TODAY but has little headroom;
  a corpus/model shift could close it. That is the standing signal that RERANKING (retrieve wide
  -> calibrated rerank score -> threshold on that) is the durable fix if headroom ever fails.
- Same-chunk collisions (nearest-but-irrelevant regions, all correctly rejected): Q6 dental and
  Q8 gym both top-match the §4 comp/benefits chunk 6123-7254; Q7 parking top-matches the §5
  equipment chunk 7220-8172 (the same chunk Q2 legitimately matches, but at 0.437 vs Q2's 0.529).
- Rate limiting: Voyage 429 on Q2/Q3/Q5/Q6/Q8 (retried at 25s, deterministic scores unaffected).
- No .env changes; floor read from the code default (settings.py). Not committed - PM review of
  the negative controls pending.
```


<!-- Appended by ADR 0004 slice 1 (OCR) — do not edit; append new runs below. -->
## OCR fixture + confidence calibration (ADR 0004 slice 1)

`neo_retrieval_benchmark_v1_scanned.pdf` — a 4-page IMAGE-ONLY PDF (zero text
layer) rendered from real handbook excerpts (annual leave / bereavement / laptop /
share options). Purpose: prove OCR'd text is searchable and calibrate the
confidence floor (`document_ocr_min_confidence`) from data, not a guess.

Config: DOCUMENT_OCR_ENABLED=true, DPI=200 (code-fixed), voyage-3.5, block_aware.

Text recovery (Tesseract 5.5.0, in the api container): **100% exact** on all four
clean pages — e.g. "Annual leave entitlement is 26 days per calendar year, in
addition to public holidays." recovered verbatim.

Per-page mean word-confidence, by scan quality (same sentence, worsening):

```
clean render            95.4 – 96.0    perfect text
light  degradation      95.9           perfect text
medium degradation      54.5           garbled ("onudenent", "calendary")
heavy  degradation      0 (no words)   auto-dropped → doc rejected as unreadable
```

Ruling (d) floor set to **60** (was provisionally 50): it sits in the wide gap
between clean scans (~95) and the garbled tier (~54.5), so it drops near-garbage
while keeping every clean scan with margin. Blank/illegible pages yield no words
and are dropped regardless. Env-tunable per corpus; lower toward 50 to admit
more marginal pages (flagged "(OCR)" + stored ocr_confidence), raise to be stricter.

Caveat: these renders are pristine (no camera/scanner noise, skew from real paper).
Genuine photographed scans typically land ~75–90; the 60 floor is conservative for
that range. Recalibrate if a real-paper corpus shows a different distribution.
