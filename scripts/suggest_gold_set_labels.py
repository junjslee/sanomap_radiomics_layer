#!/usr/bin/env python3
"""Generate label SUGGESTIONS for ``artifacts/gold_set_v1_UNLABELED.jsonl``.

This is computer-aided manual annotation per the user's hybrid approach:
Claude generates per-row label suggestions with rationale; the human
annotator (junjslee) reviews each row, accepts or overrides, and the
authoritative labels remain human-controlled.

Output columns are per ``docs/benchmark/annotation_schema.md`` v1.0.
Every suggestion carries an additional ``_suggestion_rationale`` field
explaining the labeling decision so the reviewer can spot-check fast.

Run:
    conda run -n base python scripts/suggest_gold_set_labels.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "artifacts" / "gold_set_v1_UNLABELED.jsonl"
OUTPUT = ROOT / "artifacts" / "gold_set_v1_LABELED_pass1_SUGGESTIONS.jsonl"

# Per-row labels keyed by record_id.
# Each value is a dict with: label, evidence_type, quantitative, confidence,
# evidence_span (start,end char offsets into sentence; None when N/A),
# inferred_feature_canonical, inferred_node_type, annotator_notes,
# _suggestion_rationale (review aid; not part of schema).
SUGGESTIONS: dict[str, dict] = {

    # ============================================================
    # STRATUM: accepted_edge (rows already in graph as CORRELATES_WITH)
    # ============================================================

    "f8c13e0c3f557775": {
        "label": "associated_positive",
        "evidence_type": "direct_measurement",
        "quantitative": "qualitative_only",
        "confidence": "high",
        "evidence_span": [0, 88],  # "Eubacterium is known to be enriched in patients with a higher IA-VAT burden"
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Sentence: 'Eubacterium ENRICHED in patients with HIGHER IA-VAT burden, which matches the results of this study'. Eubacterium↑ ↔ IA-VAT↑ → positive. 'matches the results of this study' = direct_measurement.",
    },

    "a16e2538de04996b": {
        "label": "associated_negative",
        "evidence_type": "direct_measurement",
        "quantitative": "qualitative_only",
        "confidence": "high",
        "evidence_span": [1, 90],
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "'sarcopenia-related DEPLETION of fecal Ruminococcus' — sarcopenia↑ ↔ Ruminococcus↓ → negative correlation. Direct study finding.",
    },

    "5fce1d6ad71b9859": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Substring filter false positive: 'Peptostreptococcus stomatis' is the labeled microbe but is NOT in this sentence. Sentence describes generic 'altered intestinal microbiota' relationship to muscle decline, not P. stomatis specifically.",
        "_suggestion_rationale": "Per § 2 schema: 'bound to a specific source sentence; the sentence is the textual evidence'. The microbe surface 'peptostreptococcus stomatis' does not appear in this sentence — only 'intestinal microbiota' does. Cannot confirm P. stomatis ↔ SMI claim from this evidence.",
    },

    "abfe76bba0b1d891": {
        "label": "associated_negative",
        "evidence_type": "direct_measurement",
        "quantitative": "qualitative_only",
        "confidence": "high",
        "evidence_span": [0, 100],
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "'Akkermansia, NEGATIVELY correlated with body weight, fat mass'. Akkermansia↑ ↔ fat_mass↓ → associated_negative. Direct measurement.",
    },

    "18b844eaa9514023": {
        "label": "unclear",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Edge #5: 'gut bacterial clpb-like gene function' is a KEGG gene-function annotation, not a microbe. Per § 6.8, label as unclear. UMLS gate (Task 1) correctly drops this — confirmed by audit (similarity 0.799 < 0.850).",
        "_suggestion_rationale": "Schema § 6.8 entity-type error pattern. The biological claim itself (ClpB-like gene → decreased body fat) is associated_negative, but the entity is wrong-type, so primary label is unclear per schema.",
    },

    "bcd4cdb39a0f0ffa": {
        "label": "associated_negative",
        "evidence_type": "citation_of_other_paper",
        "quantitative": "qualitative_only",
        "confidence": "medium",
        "evidence_span": [0, 195],
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Microbe surface 'bacteriodetes' is a typo for 'Bacteroidetes'. UMLS gate dropped this with no_umls_match (audit confirmed). Biological claim is valid: Bacteroidetes proportion lower in obese.",
        "_suggestion_rationale": "'Bacteriodetes...is LOWER in obese persons' → Bacteroidetes ↑ ↔ body_fat ↓. Cite-of-prior-work language: 'Recent studies have shown'.",
    },

    "92d49fc51360c413": {
        "label": "associated_unsigned",
        "evidence_type": "citation_of_other_paper",
        "quantitative": "qualitative_only",
        "confidence": "medium",
        "evidence_span": [0, 220],
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "'importance of [Lactobacillus spp]... on fat mass development' — direction unspecified. 'Several reports have demonstrated' = citation_of_other_paper.",
    },

    "8cff540f1fdc680f": {
        "label": "associated_unsigned",
        "evidence_type": "citation_of_other_paper",
        "quantitative": "qualitative_only",
        "confidence": "medium",
        "evidence_span": [0, 220],
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Multi-microbe sentence per § 6.4; same sentence as record f8cff540f1fdc680f and 92d49fc51360c413, label per microbe.",
        "_suggestion_rationale": "Same sentence as previous row, microbe = bifidobacterium spp. Same logic: 'importance of selected bacteria' on fat mass — unsigned.",
    },

    # ============================================================
    # STRATUM: gemini_rejected (Gemini self-consistency rejected these)
    # ============================================================

    "4914da8f0597c535": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Sentence is about HERITABILITY of microbial taxa (Actinobacteria heritable), not about Actinobacteria↔VAT direct association. VAT mentioned only in adjacent clause about Th2 cells. Co-occurrence, not asserted relation. Gemini correctly rejected.",
    },

    "1f794f0b028e4209": {
        "label": "associated_negative",
        "evidence_type": "hypothesis",
        "quantitative": "qualitative_only",
        "confidence": "medium",
        "evidence_span": [262, 462],
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Heavy hedging ('Both may act synergistically'). Per § 6.6 causal verb 'mitigate' implies inverse relationship. Gemini may have rejected due to hedging.",
        "_suggestion_rationale": "'Faecalibacterium... may act synergistically through gut-muscle-nerve axis to MITIGATE... DPNS [sarcopenia component]'. Per § 6.6, causal 'mitigate' = inverse. evidence_type=hypothesis due to 'may'.",
    },

    "7b14b80f4f63074d": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "medium",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Sentence: 'Ileal Proteobacteria... exhibit a NEGATIVE association with insulin sensitivity'. The Proteobacteria-VAT link is NOT directly asserted; VAT appears only in earlier clause about Th2 cells. Co-occurrence. Gemini correctly rejected.",
    },

    "6a31a99cae3ab6c4": {
        "label": "not_associated",
        "evidence_type": "methods_description",
        "quantitative": "has_p_value",
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Baseline characteristics table. p-values are placebo-vs-treatment group balance checks (p=0.908 for muscle mass, p=0.187 for fat mass — all NS), NOT microbe-feature correlations. evidence_type=methods_description.",
    },

    "7cfdd734ce31d418": {
        "label": "unclear",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Entity-type error per § 6.8: 'fusobacterium - colonized microniches' — microniche is anatomical/structural, not a microbe. UMLS gate would catch.",
        "_suggestion_rationale": "Schema § 6.8 entity-type error. Sentence describes spatial transcriptomics methods, no SMI claim either way.",
    },

    # ============================================================
    # STRATUM: vocab_excluded (extended-keyword features outside _FEATURE_VOCAB)
    # ============================================================

    "d40a64fb6bbb7a12": {
        "label": "associated_negative",
        "evidence_type": "citation_of_other_paper",
        "quantitative": "qualitative_only",
        "confidence": "medium",
        "evidence_span": [69, 175],
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Genus-vs-species mismatch: labeled microbe is 'lactobacillus' (genus), sentence claim is about 'Lactobacillus reuteri' (species). Genus contains the species, so claim transitively applies.",
        "_suggestion_rationale": "'Lactobacillus reuteri was beneficial for [cachexia] PREVENTION'. Per § 6.6, 'prevention' = inverse cause→effect. L.reuteri↑ ↔ cachexia↓.",
    },

    "e0654b9a960964b9": {
        "label": "associated_negative",
        "evidence_type": "direct_measurement",
        "quantitative": "qualitative_only",
        "confidence": "high",
        "evidence_span": [0, 64],
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "RESULTS section header: 'Lactobacillus reuteri INHIBITS cancer-associated cachexia'. § 6.6 inverse relationship. L.reuteri↑ ↔ cachexia↓.",
    },

    "5e5b54f7b93b92b0": {
        "label": "associated_negative",
        "evidence_type": "citation_of_other_paper",
        "quantitative": "qualitative_only",
        "confidence": "high",
        "evidence_span": [21, 130],
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "'Eubacterium [rectale and eligens] positively linked to REDUCED frailty' — Eubacterium↑ ↔ frailty↓. Per § 6.6, 'reduced frailty' is the outcome direction; net relationship is negative.",
    },

    # ============================================================
    # STRATUM: recall_probe (no candidate_feature_canonical pre-specified)
    # ============================================================

    "430000b1cd7caae8": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "'alterations of Lactobacillus in obesity'. Direction unspecified. Obesity is a disease, not a body-comp/radiomic feature. No imaging feature asserted.",
    },

    "3862efed1a9d2d48": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "medium",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "'anti-obesity effects... lipid metabolism' — generic mechanism, not a specific imaging-derived feature. Lipid metabolism is biochemical, not imaging.",
    },

    "5e0130347daf06cc": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "F/B ratio + obesity context. No body-composition imaging feature explicitly mentioned.",
    },

    "2f5e4c9dd4d854b3": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Bacteroidetes-obesity link only. No specific imaging feature.",
    },

    "5b9e031f0ee108f6": {
        "label": "associated_negative",
        "evidence_type": "citation_of_other_paper",
        "quantitative": "qualitative_only",
        "confidence": "medium",
        "evidence_span": [115, 290],
        "inferred_feature_canonical": "waist_hip_ratio",
        "inferred_node_type": "BodyCompositionFeature",
        "annotator_notes": "WHR is anthropometric (not strictly imaging-derived). Schema treats body composition broadly per existing accepted_edge precedent (body_fat, body_weight). Reviewer: confirm if WHR fits BodyCompositionFeature scope.",
        "_suggestion_rationale": "'B. lactis [supplementation]... led to clinically significant DECREASE in WHR' — § 6.6 causal verb, inverse direction. B. lactis↑ ↔ WHR↓.",
    },

    "bc02724c1cb8c8fa": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "medium",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Generic 'live bacterium' microbe surface (entity error / placeholder).",
        "_suggestion_rationale": "Truncated sentence about A. muciniphila strain protective effects vs HFD obesity. Microbe surface 'live bacterium' is a placeholder. No specific imaging feature.",
    },

    "de8fcb1ca57ab720": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Microbe surface 'escherichi' is truncated/malformed.",
        "_suggestion_rationale": "Microbial enrichment after intervention. No imaging feature.",
    },

    "2d8236f16894c03d": {
        "label": "not_associated",
        "evidence_type": "methods_description",
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Abbreviations / ethics statement boilerplate. No claim.",
    },

    "7615413014990ad7": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Microbe surface 'streptoco' is truncated.",
        "_suggestion_rationale": "F/B ratio + obesity-microbiota hallmark. No specific imaging feature.",
    },

    "c79fe0f679f3007a": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "HFD induces obesity + bifidobacteria decrease. No specific imaging feature.",
    },

    "9e3682f6722a3fbd": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Title text: 'Anti-obesity effect of Lactobacillus'. Generic anti-obesity claim. No imaging feature.",
    },

    "930487b50601177a": {
        "label": "not_associated",
        "evidence_type": "methods_description",
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Microbe surface 'os odoribacter splanchnicus' has artifactual 'Os' prefix from abbreviation list ('Os Odoribacter splanchnicus').",
        "_suggestion_rationale": "Abbreviations / supplementary material boilerplate. No claim.",
    },

    "b3a72c74027e1662": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "F. nucleatum location/translocation in CRC tumors. No imaging feature.",
    },

    "e4c9fc61f452de6e": {
        "label": "associated_negative",
        "evidence_type": "citation_of_other_paper",
        "quantitative": "qualitative_only",
        "confidence": "medium",
        "evidence_span": [115, 290],
        "inferred_feature_canonical": "waist_hip_ratio",
        "inferred_node_type": "BodyCompositionFeature",
        "annotator_notes": "Same sentence as 5b9e031f0ee108f6, microbe = bifidobacterium bifidum. WHR scope question stands.",
        "_suggestion_rationale": "Multi-microbe sentence § 6.4. Same WHR-decrease logic.",
    },

    "1b8879157fa3e30f": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Bifidobacterium as therapeutic against metabolic syndrome / DIO. No specific imaging feature.",
    },

    "307c316a96a8f88d": {
        "label": "associated_negative",
        "evidence_type": "hypothesis",
        "quantitative": "qualitative_only",
        "confidence": "medium",
        "evidence_span": [37, 240],
        "inferred_feature_canonical": "bone_mineral_density",
        "inferred_node_type": "BodyCompositionFeature",
        "annotator_notes": "Bone loss → decreased BMD. Hedged via 'we propose... may'. evidence_type=hypothesis.",
        "_suggestion_rationale": "'high Gammaproteobacteria... result in inflammation-induced BONE LOSS'. Bone loss = BMD↓. G.proteobacteria↑ ↔ BMD↓. Hedged.",
    },

    "8d20ce1422d1e670": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Title: 'Exosomes secreted by F.nucleatum-infected colon cancer'. No imaging feature.",
    },

    "2f079ba04de88819": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Parabacteroides reduction in obesity/metabolic syndrome. No imaging feature.",
    },

    "b71f29e0de6f3ae1": {
        "label": "unclear",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Entity-type error per § 6.8: 'pro-inflammatory bacterial products' = LPS (a metabolite/molecule), not a microbe.",
        "_suggestion_rationale": "Schema § 6.8 entity-type error: bacterial products are metabolites, not microbes.",
    },

    "0b2f558a2e6e6e9b": {
        "label": "associated_positive",
        "evidence_type": "citation_of_other_paper",
        "quantitative": "qualitative_only",
        "confidence": "high",
        "evidence_span": [165, 248],
        "inferred_feature_canonical": "bmi",
        "inferred_node_type": "BodyCompositionFeature",
        "annotator_notes": "BMI is anthropometric not imaging. Reviewer: confirm scope.",
        "_suggestion_rationale": "'Bacteroides... abundance POSITIVELY correlated with BMI'. Bacteroides↑ ↔ BMI↑. Citation: '[25]'.",
    },

    "6598cbdc13dd421f": {
        "label": "unclear",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Edge #5 variant: 'gut bacterial clpb-like gene' is gene-function, not a microbe. UMLS gate catches.",
        "_suggestion_rationale": "§ 6.8 entity-type error.",
    },

    "642eeb8d2dc598bd": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "medium",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Truncated sentence (cuts off mid-clause).",
        "_suggestion_rationale": "Truncated sentence about inflammation/obesity/insulin resistance. No imaging feature evident.",
    },

    "e78b39a463c77dcd": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Microbe-disease association (NAFLD, HCC). NAFLD is the disease; would-be feature would be liver_fat_fraction but it's not asserted.",
    },

    "62cbb49790e8f213": {
        "label": "not_associated",
        "evidence_type": "methods_description",
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Abbreviations + author contributions list. No claim.",
    },

    "82628b6a2e5a9510": {
        "label": "unclear",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Entity-type error per § 6.8: 'penicillin-streptomycin' is an antibiotic mixture, not a microbe.",
        "_suggestion_rationale": "Cell-culture media boilerplate; antibiotic, not microbe.",
    },

    "6014aaae780d1b61": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "medium",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Actinobacteria-obesity link. No imaging feature.",
    },

    "26e5ce137b0d9a59": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Proteobacteria increase in cancer initiation context. No imaging feature.",
    },

    "824fa73a6f0aa2c4": {
        "label": "associated_unsigned",
        "evidence_type": "direct_measurement",
        "quantitative": "qualitative_only",
        "confidence": "medium",
        "evidence_span": [0, 220],
        "inferred_feature_canonical": "trunk_fat_distribution",
        "inferred_node_type": "BodyCompositionFeature",
        "annotator_notes": "Coprococcus_sp5 is one of 16 MGS associated with trunk-fat distribution. Direction not stated in this excerpt.",
        "_suggestion_rationale": "'16 MGS associated with trunk-fat distribution, including... Coprococcus_sp5'. Asserts association; direction unspecified here.",
    },

    "14208c05a4b6061a": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Title text. Anti-obesity claim, no specific imaging feature.",
    },

    "f5ae9ff4a1be993b": {
        "label": "associated_negative",
        "evidence_type": "citation_of_other_paper",
        "quantitative": "qualitative_only",
        "confidence": "high",
        "evidence_span": [222, 410],
        "inferred_feature_canonical": "bmi",
        "inferred_node_type": "BodyCompositionFeature",
        "annotator_notes": "BMI scope question (anthropometric vs imaging) — reviewer to confirm.",
        "_suggestion_rationale": "'Methanobrevibacter smithii... ENRICHED in individuals with LOW body mass index'. M.s.↑ ↔ BMI↓. Citation: 'a large twin study.38'.",
    },

    # ============================================================
    # STRATUM: random_co_occurrence (random sentence-level co-occurrence)
    # ============================================================

    "bfd6de0cc972d160": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "BMI used to define population (BMI ≥ 40 → morbid obesity); the assertion is about BMI→infection risk, not microbe↔BMI. Co-occurrence only.",
    },

    "a43c53b3053847d5": {
        "label": "unclear",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "medium",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Entity-type error per § 6.8: 'bacteroidetes ratio' is a derived ratio, not a microbe.",
        "_suggestion_rationale": "§ 6.8 — 'ratio' is not an entity.",
    },

    "b2d1e0395e083f23": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "medium",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Actinobacteria abundance vs obesity context. No imaging feature.",
    },

    "cb27156616a4f715": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Peptostreptococcaceae-ALT/AST/GGT/CRP (liver enzymes / CRP, biochemical). Not imaging features.",
    },

    "f364a59ef6aa19a5": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "medium",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Lactobacillus gasseri anti-obesity / energy expenditure. No imaging feature.",
    },

    "91655ab9d223b281": {
        "label": "associated_negative",
        "evidence_type": "citation_of_other_paper",
        "quantitative": "qualitative_only",
        "confidence": "medium",
        "evidence_span": [115, 290],
        "inferred_feature_canonical": "waist_hip_ratio",
        "inferred_node_type": "BodyCompositionFeature",
        "annotator_notes": "Same sentence as 5b9e031f0ee108f6 / e4c9fc61f452de6e. Stratum is random_co_occurrence here but the sentence DOES carry a substantive claim.",
        "_suggestion_rationale": "Same WHR-decrease logic. Note: same sentence appears in different strata with different microbes — sampler artifact.",
    },

    "9691e2982585739d": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Same as 8d20ce1422d1e670 — F.n. exosomes title. No imaging feature.",
    },

    "d9571660ecf40710": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Same as de8fcb1ca57ab720 — microbial enrichment after synbiotics. No imaging feature.",
    },

    "5e27194d441c7763": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Same as 7615413014990ad7. No imaging feature.",
    },

    "45b7d25da7f2b41d": {
        "label": "not_associated",
        "evidence_type": "methods_description",
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Trial OBJECTIVE statement (not a finding). 'evaluate the effects... in relation to changes in body composition'. No specific feature claim asserted.",
    },

    "fa9396872fdd5dea": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Same as 2f079ba04de88819. No imaging feature.",
    },

    "2bbe60c4b2a9883d": {
        "label": "unclear",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Edge #5 entity-type error per § 6.8.",
        "_suggestion_rationale": "Same logic as 18b844eaa9514023 — gene-function, not microbe.",
    },

    "ac3b40c1d2e45300": {
        "label": "unclear",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "Edge #5 variant entity-type error per § 6.8.",
        "_suggestion_rationale": "Same logic as 6598cbdc13dd421f.",
    },

    "216253ec41a66ae2": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "medium",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Same truncated sentence as 642eeb8d2dc598bd.",
    },

    "363d7dbf3b7b8bf8": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Same as 4914da8f0597c535 — heritability sentence.",
    },

    "40a9b9a5b4ddad2b": {
        "label": "not_associated",
        "evidence_type": "methods_description",
        "quantitative": "has_p_value",
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Same as 6a31a99cae3ab6c4 — baseline characteristics table.",
    },

    "68981153870928ea": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Same as 430000b1cd7caae8.",
    },

    "6744a5bbf248e63c": {
        "label": "not_associated",
        "evidence_type": "methods_description",
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Same as 2d8236f16894c03d — abbreviations / ethics text.",
    },

    "1db2d78ea5b94ac1": {
        "label": "not_associated",
        "evidence_type": None,
        "quantitative": None,
        "confidence": "high",
        "evidence_span": None,
        "inferred_feature_canonical": None,
        "inferred_node_type": None,
        "annotator_notes": "",
        "_suggestion_rationale": "Title: 'Liver abscess caused by Cutibacterium... after TACE for HCC'. Disease/intervention context. No imaging feature.",
    },

    "1b8deaecd521e3b5": {
        "label": "no_association_explicit",
        "evidence_type": "direct_measurement",
        "quantitative": "has_p_value",
        "confidence": "high",
        "evidence_span": [0, 250],
        "inferred_feature_canonical": "bmi",
        "inferred_node_type": "BodyCompositionFeature",
        "annotator_notes": "Table data: F. nucleatum +/- groups, BMI 27.06±4.60 vs 25.67±2.78, p=0.18 (not significant).",
        "_suggestion_rationale": "Per § 6.3 negation: explicit null finding (p=0.18 NS) is no_association_explicit, NOT not_associated. Note: Tumor size p=0.04* is significant but tumor size is not body composition.",
    },

}


def main() -> int:
    if not INPUT.exists():
        print(f"ERROR: input not found: {INPUT}")
        return 1

    rows = [json.loads(line) for line in INPUT.read_text().splitlines() if line.strip()]
    print(f"Loaded {len(rows)} rows from {INPUT.name}")

    missing: list[str] = []
    out_rows: list[dict] = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for rec in rows:
        rid = rec["record_id"]
        sug = SUGGESTIONS.get(rid)
        if sug is None:
            missing.append(rid)
            continue
        merged = dict(rec)
        merged.update({
            "label": sug["label"],
            "evidence_type": sug["evidence_type"],
            "quantitative": sug["quantitative"],
            "confidence": sug["confidence"],
            "evidence_span": sug["evidence_span"],
            "inferred_feature_canonical": sug["inferred_feature_canonical"],
            "inferred_node_type": sug["inferred_node_type"],
            "annotator_notes": sug["annotator_notes"],
            "labeled_at": now_iso,
            "label_pass": 1,
            "_suggestion_rationale": sug["_suggestion_rationale"],
            "_suggested_by": "claude-opus-4.7-1m (computer-aided manual annotation)",
        })
        out_rows.append(merged)

    if missing:
        print(f"WARNING: {len(missing)} records have no suggestion: {missing[:5]}...")

    OUTPUT.write_text("\n".join(json.dumps(r) for r in out_rows) + "\n")
    print(f"Wrote {len(out_rows)} suggestions → {OUTPUT}")

    # Summary
    from collections import Counter
    c = Counter(r["label"] for r in out_rows)
    print("\nLabel distribution:")
    for lab, n in c.most_common():
        print(f"  {lab}: {n}")
    s = Counter(r["stratum"] for r in out_rows)
    print("\nStratum coverage:")
    for st, n in s.most_common():
        print(f"  {st}: {n}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
