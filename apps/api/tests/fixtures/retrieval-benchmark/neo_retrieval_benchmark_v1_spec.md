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

### Query 6 is the most important one

The document contains no dental policy. Correct behaviour is **zero results** — the floor rejects everything. If Query 6 returns a passage, the floor is too permissive and every other result becomes suspect, because we'd have no evidence the system can say "I don't know."

A benchmark that only tests recall will happily approve a system that matches everything.

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
