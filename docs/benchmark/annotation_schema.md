# Body Composition Correlation Annotation Schema v1.0

**Status:** locked — changes require version bump (v1.1, v2.0, …) and
re-annotation of any rows whose interpretation changes.

**Effective date:** 2026-05-04

**Owner:** junjslee (single annotator; intra-annotator IAA via 2-week
temporal re-labeling)

---

## 1. Purpose

This schema defines what an annotator marks for each row of
`artifacts/gold_set_v1_UNLABELED.jsonl`. It exists so that:

1. The labels are interpretable years from now without reading source
   code or chat history.
2. Two passes over the same row (the annotator labels, waits 2 weeks,
   re-labels) produce comparable Cohen's κ — the schema must be
   sharp enough that the same person agrees with their past self.
3. The labels can be released alongside the codebase so external
   reviewers can re-annotate independently and produce real
   inter-annotator κ.

---

## 2. Unit of annotation

Each row is one **triple** of:

```
(PMID, microbe_surface, candidate_feature_canonical)
```

bound to a specific source sentence. The triple is the relation under
test; the sentence is the textual evidence. If a sentence makes the
same claim about multiple microbes, the sampling pipeline produces one
row per microbe — never label a sentence "as a whole."

For some strata (random, recall_probe), `candidate_feature_canonical`
may be `null` because the sampling step did not specify a feature. In
that case the annotator first identifies whether **any** body-composition
or radiomic feature appears in the sentence, fills in the inferred
canonical, then labels — see § 5.

---

## 3. Primary label (REQUIRED, mutually exclusive)

Exactly one of:

| Label | Meaning | Example |
|---|---|---|
| `associated_positive` | Sentence states/implies microbe and feature are **positively** correlated. Higher microbe → higher feature, or lower microbe → lower feature. | "*Akkermansia* abundance was positively correlated with skeletal muscle index (r = 0.42, p = 0.01)." |
| `associated_negative` | Sentence states/implies **negative** correlation (opposite directions). | "*Bacteroides* was negatively correlated with VAT (r = -0.51)." |
| `associated_unsigned` | Sentence asserts an association but does not specify direction. | "Microbiome composition was associated with sarcopenia status." |
| `no_association_explicit` | Sentence explicitly reports a NULL association. This is graph-relevant evidence and is tracked separately from "no claim made." | "No significant correlation was found between *Bifidobacterium* and SMI (r = 0.04, p = 0.78)." |
| `not_associated` | Microbe and feature merely co-occur in the sentence; no relationship is described. | "We measured both microbiome and body composition in the same cohort." |
| `unclear` | Sentence is genuinely ambiguous. Cannot label without external context. | "These results are consistent with prior findings on microbe-muscle interactions." |

**Target rate of `unclear`: < 10%.** If you are using `unclear` more
than 10% of the time, the schema needs revision (file as a v1.1
change, not a per-row workaround).

---

## 4. Secondary labels (REQUIRED for `associated_*` and `no_association_explicit`; OPTIONAL otherwise)

### 4.1 `evidence_type`

Where does the claim live in the publication structure?

- `direct_measurement` — paper reports its own measurement (e.g., "we
  measured … and found r = …").
- `citation_of_other_paper` — claim is asserted in this paper's text but
  attributed to another study ("Smith et al. reported …").
- `hypothesis` — hedged or speculative language ("may influence",
  "could be associated", "suggests").
- `methods_description` — describes data collection or technique without
  asserting an association ("we extracted SMI from …").
- `background_review` — review-of-prior-work boilerplate.

### 4.2 `quantitative`

Strongest quantitative claim in the sentence:

- `has_correlation_coef` — names a Pearson/Spearman r or ρ with value.
- `has_p_value` — explicit p-value (with or without effect size).
- `has_effect_size` — OR/HR/β/Δ/regression coefficient with value.
- `qualitative_only` — words but no numbers (e.g., "increased",
  "depleted", "enriched").

### 4.3 `confidence`

Annotator's confidence in the primary label:

- `high` — the label is obvious, takes < 30s to decide.
- `medium` — required reading the sentence twice or checking the
  surrounding context.
- `low` — borderline call, kept rather than marked `unclear`.

---

## 5. Span field (REQUIRED)

`evidence_span: [start, end]` — character offsets into the sentence
that carry the assertion. For sentences with multiple clauses, prefer
the **shortest contiguous span** that supports the label.

For `not_associated` / `unclear`: span may be `null`.

For rows with `candidate_feature_canonical: null` (random and
recall_probe strata), the annotator additionally fills:

- `inferred_feature_canonical` — the body-composition or radiomic
  feature mentioned in the sentence, in canonical snake_case form
  (e.g., `psoas_muscle_area`). If no feature is mentioned, leave
  `null` and label as `not_associated`.
- `inferred_node_type` — `BodyCompositionFeature` | `RadiomicFeature`.

The point of these strata is to discover features outside the current
vocab; treat the inferred_feature_canonical as a research output, not
just a label cell.

---

## 6. Edge case decisions (LOCKED)

These must not drift between annotation passes.

### 6.1 Hedged language
"*Akkermansia* may influence body fat" →
`associated_unsigned`, `evidence_type=hypothesis`.
Hedging affects evidence_type, not the primary label.

### 6.2 Citations of prior work
"Smith et al. reported that *Bacteroides* correlates with VAT" →
label by what the cited claim describes
(here: `associated_unsigned`); set `evidence_type=citation_of_other_paper`.
The paper is asserting the claim into its own narrative.

### 6.3 Negation
"No significant association was found between … and SMI" →
`no_association_explicit`, **not** `not_associated`.
Null findings are evidence; mere co-occurrence is not.

### 6.4 Multi-microbe sentences
"*Bacteroides* and *Akkermansia* were both correlated with VAT" →
the sampling step produces one row per microbe; label each
independently. Direction may differ between microbes.

### 6.5 Compound features
"muscle mass and function" → if the feature canonicals resolve to two
distinct concepts (e.g., `skeletal_muscle_mass` and
`muscle_function`), the sampling step produces one row per feature.
If the candidate_feature_canonical names only one of them and the
sentence supports it, label `associated_*`.

### 6.6 Direction inversion in causal language
"*Akkermansia* prevents fat accumulation" → `associated_negative`.
Causal verbs ("prevents", "reduces", "inhibits") imply inverse
correlation between cause and effect; label by the **net direction
of the relationship**, not the verb sign.

### 6.7 Surrogate features
"reduced lean body mass" used in a sentence whose candidate_feature is
`skeletal_muscle_index` → if the sampling produced this row, the substring
filter conflated lean mass with SMI. Label what the sentence actually
says (about lean body mass) and update `inferred_feature_canonical`
to `lean_body_mass`. The mismatch is itself a finding for the
vocab/retrieval comparison.

### 6.8 Microbe surface mismatch
If `microbe_surface` is `gut bacterial clpb-like gene function` (the
Edge #5 case), the entity is not actually a microbe — label as
`unclear` with `annotator_notes: "entity-type error from upstream NER"`.
These rows test the UMLS gate: a properly gated pipeline would
never produce this candidate.

---

## 7. Inter-annotator agreement protocol

### 7.1 First pass
Annotator labels every non-`unclear` row.
Time budget: ~1.5 min/row × 150 rows ≈ 4 hours total.
Recommended: do 30-50 rows per session, max 3 sessions per week.

### 7.2 Calibration window
Wait **14 calendar days** between the first pass and the second pass
on the same rows. The wait is non-negotiable: shorter intervals leak
short-term memory; the goal is to test whether the schema is sharp
enough that the same annotator's *future* judgment matches.

### 7.3 Second pass
Re-label the same 150 rows **without consulting the first pass labels**.
If feasible, randomize the row order to break sequential context.

### 7.4 Agreement computation
Compute Cohen's κ on the **primary label** (6-class) and separately
on the **binary collapse** (`associated_*` vs everything else).

```
κ = (P_o - P_e) / (1 - P_e)
```

where `P_o` is observed agreement and `P_e` is expected agreement
under random labeling weighted by class frequency.

### 7.5 Acceptance threshold
- κ ≥ 0.80 (Landis & Koch "substantial") → schema is acceptable, lock.
- 0.60 ≤ κ < 0.80 → schema needs targeted clarification on disagreement
  cases; revise (v1.1) and re-label only conflicted rows.
- κ < 0.60 → schema is structurally unclear; revise (v2.0) and
  re-label all rows.

### 7.6 Disagreement audit
Whatever κ is, write `docs/benchmark/IAA_v1.md` listing:
- κ on primary label (6-class)
- κ on binary collapse
- top-5 disagreement-by-label-pair counts
- one paragraph per disagreement-pair explaining the root cause

This audit is the limitation citation for the paper.

---

## 8. Label slots in the JSONL row

Each unlabeled row carries the slots below as `null`. Fill them in
during annotation. The evaluator (`src/benchmark/evaluate.py`) reads
exactly these field names:

```jsonc
{
  // populated by the sampling script — DO NOT EDIT
  "record_id": "abc123…",
  "pmid": "37499955",
  "stratum": "gemini_rejected",
  "sentence": "…",
  "microbe": "Akkermansia",
  "candidate_feature_canonical": "visceral_adipose_tissue",
  "candidate_feature_node_type": "BodyCompositionFeature",
  "pipeline_state": "rejected_by_gemini",

  // filled by the annotator
  "label": null,                          // see § 3
  "evidence_type": null,                  // see § 4.1
  "quantitative": null,                   // see § 4.2
  "confidence": null,                     // see § 4.3
  "evidence_span": null,                  // see § 5
  "inferred_feature_canonical": null,     // for null-feature strata
  "inferred_node_type": null,             // for null-feature strata
  "annotator_notes": "",                  // free-text
  "labeled_at": null,                     // ISO 8601, set when label added
  "label_pass": null                      // 1 (first pass) | 2 (re-label)
}
```

Both passes are saved as separate JSONL files:
- `artifacts/gold_set_v1_LABELED_pass1.jsonl`
- `artifacts/gold_set_v1_LABELED_pass2.jsonl`

The evaluator scores against pass 1 by default; the IAA computation
uses both.

---

## 9. Schema versioning

This file is `v1.0`. Every locked decision in § 6 plus the label
ontology in § 3 are fixed at this version. Future changes:

- v1.x — clarification, no semantic shift (rarely needs re-labeling).
- v2.x — semantic shift in label set or scoring rules
  (requires full re-labeling).

When updating, append a row to the table below.

| Version | Date | Author | Change |
|---|---|---|---|
| v1.0 | 2026-05-04 | junjslee | Initial schema. |
