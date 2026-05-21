# Limitations Patch — ready for insertion into `paper_sanomap_radiomics_layer.tex`

Drafted 2026-05-21. To be inserted into the manuscript as a paragraph or short
subsection within the Methods / Discussion / Limitations section (the
manuscript already names two limits in the abstract; this patch makes the
governance + ontology + data-uniformity gaps explicit).

---

## Suggested LaTeX block

```latex
\subsection{Scope and Coverage Limits}
\label{sec:limitations}

We name the limits this layer carries by construction so reviewers can weigh
them directly. \textbf{Annotator coverage.} Acceptance metrics rest on a
single-annotator gold set with intra-annotator IAA via 14-day temporal
re-labeling; Cohen's $\kappa$ measures consistency, not external validity.
\textbf{Vision-track yield.} Only one figure-derived correlation
(\textit{Prevotella nigrescens}\,$\leftrightarrow$\,GLCM\_Correlation, PMID
37894458) survived the post-2026-05-07 gate-chain audit; this is presented
as a methodological case study, not as a confirmed biological finding.
\textbf{Ontological grounding is uneven.} Microbe entities are grounded via
UMLS Semantic Type Identifiers (T007, T194, T204, T005) and CUIs; other node
classes carry free-text labels. Diseases are not bound to MONDO / DOID;
BodyLocation nodes are not bound to FMA / UBERON / RadLex; ImagingModality
nodes are not bound to DICOM modality codes; RadiomicFeature names are
IBSI-aligned in vocabulary but not as URI references. A v2 ontology binding
pass is a documented follow-on.
\textbf{Signed microbe--disease confidence is uniform.} All 29
\texttt{POSITIVELY\_CORRELATED\_WITH} and \texttt{NEGATIVELY\_CORRELATED\_WITH}
edges carry the relation extractor's default confidence (0.7). Per-edge
confidence calibration is a downstream task, planned for after the Pass-2
gold set lands.
\textbf{Scope of ``imaging phenotype.''} This layer organizes imaging-derived
phenotype evidence at two granularities: IBSI-aligned radiomic features
(precision pole — texture and shape statistics) and clinical body-composition
biomarkers (coverage pole — SMI, VAT, sarcopenia, myosteatosis, etc.). Body
composition is, in current literature, the dominant evidence modality for
microbiome--imaging correlations; excluding it would walk away from
$\sim$95\% of the relevant evidence base.
```

---

## Why each limit lands here, not in an Appendix

| Limit | Why surface, not bury |
|---|---|
| Single-annotator IAA | Methods reviewers will ask first. The abstract already alludes; the body should commit. |
| Vision yield 1/14 | Reviewer expectation must be set BEFORE they read the vision section. |
| Ontology grounding uneven | Semantic-web reviewers will flag this; pre-empting builds credibility. |
| Confidence uniform | A query button advertises "strongest confidence first" — we made that an honest list and dropped the sort claim in v1 of the explorer. Manuscript should match. |
| Body-comp scope | This is the framing that protects against the "but radiomics doesn't include SMI" objection. |

---

## Insertion point

Recommended location in `paper_sanomap_radiomics_layer.tex`:

- AFTER the Results section's discussion of measured P/R/F1 (gated; Pass-2)
- BEFORE the Conclusion or Future Work section
- Reuse the abstract's existing "deliberately scoped" vocabulary so tone stays
  consistent ("we name the limits this layer carries by construction").
