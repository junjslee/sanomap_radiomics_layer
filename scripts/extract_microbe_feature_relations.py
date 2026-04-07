#!/usr/bin/env python3
"""Extract microbe→body-composition-feature CORRELATES_WITH edges from text.

Scans entity_sentences JSONL for sentences where a microbe entity and a body
composition feature co-occur, then runs Gemini self-consistency classification
to determine whether the sentence describes a direct association.

Accepted pairs become CORRELATES_WITH edges in the graph, closing the three-hop
path: Microbe →[CORRELATES_WITH]→ Feature →[ASSOCIATED_WITH]→ Disease.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

# ── Feature vocabulary ──────────────────────────────────────────────
# Maps surface forms → (canonical_name, node_type) so text-derived edges
# use the exact same entity names as existing ASSOCIATED_WITH edges.

_FEATURE_VOCAB: list[tuple[str, str, str]] = [
    # (alias, canonical, node_type)
    ("sarcopenia", "sarcopenia", "BodyCompositionFeature"),
    ("sarcopenic", "sarcopenia", "BodyCompositionFeature"),
    ("skeletal muscle index", "skeletal_muscle_index", "BodyCompositionFeature"),
    ("smi", "skeletal_muscle_index", "BodyCompositionFeature"),
    ("visceral adipose tissue", "visceral_adipose_tissue", "BodyCompositionFeature"),
    ("visceral adipose", "visceral_adipose_tissue", "BodyCompositionFeature"),
    ("visceral adiposity", "visceral_adipose_tissue", "BodyCompositionFeature"),
    ("visceral fat", "visceral_adipose_tissue", "BodyCompositionFeature"),
    ("vat", "visceral_adipose_tissue", "BodyCompositionFeature"),
    ("subcutaneous adipose tissue", "subcutaneous_adipose_tissue", "BodyCompositionFeature"),
    ("subcutaneous adipose", "subcutaneous_adipose_tissue", "BodyCompositionFeature"),
    ("subcutaneous fat", "subcutaneous_adipose_tissue", "BodyCompositionFeature"),
    ("sat", "subcutaneous_adipose_tissue", "BodyCompositionFeature"),
    ("myosteatosis", "myosteatosis", "BodyCompositionFeature"),
    ("muscle attenuation", "muscle_attenuation", "BodyCompositionFeature"),
    ("body fat", "body_fat", "BodyCompositionFeature"),
    ("fat mass", "body_fat", "BodyCompositionFeature"),
    ("total fat", "body_fat", "BodyCompositionFeature"),
    ("body fat percentage", "body_fat", "BodyCompositionFeature"),
    ("bone mineral density", "bone_mineral_density", "BodyCompositionFeature"),
    ("bmd", "bone_mineral_density", "BodyCompositionFeature"),
    ("muscle mass", "skeletal_muscle_index", "BodyCompositionFeature"),
    ("lean mass", "skeletal_muscle_index", "BodyCompositionFeature"),
    ("lean body mass", "skeletal_muscle_index", "BodyCompositionFeature"),
]

# Sort longest-first so "visceral adipose tissue" matches before "visceral adipose"
_FEATURE_VOCAB.sort(key=lambda t: len(t[0]), reverse=True)

# Abbreviations that need word-boundary matching to avoid false positives
_ABBREV_ALIASES = {"smi", "vat", "sat", "bmd"}

# ── Gemini API ──────────────────────────────────────────────────────

_GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

_SYSTEM_PROMPT = (
    "You are an expert microbiologist analyzing biomedical literature. "
    "Given a sentence from a research paper, determine whether it describes "
    "a direct association between a specific microbe and a specific body "
    "composition or imaging feature. "
    "Answer 'associated' ONLY if the sentence states or implies a direct "
    "quantitative or qualitative link (correlation, enrichment/depletion "
    "co-occurring with the feature, causal influence on the feature). "
    "Answer 'unrelated' if: the microbe and feature merely co-occur in the "
    "same sentence without a described association, if the link is indirect "
    "through a third variable, or if the sentence is a general background statement. "
    "Reply with exactly one word: associated or unrelated."
)

_USER_TEMPLATE = (
    "Sentence: {sentence}\n\n"
    "Microbe: {microbe}\n"
    "Body composition feature: {feature}\n\n"
    "Is there a direct association between the microbe and the feature "
    "described in this sentence? Reply: associated or unrelated."
)


def _call_gemini(
    *,
    model_id: str,
    api_key: str,
    sentence: str,
    microbe: str,
    feature: str,
    temperature: float = 0.7,
) -> str:
    """Single Gemini API call. Returns 'associated' or 'unrelated'."""
    user_msg = _USER_TEMPLATE.format(
        sentence=sentence, microbe=microbe, feature=feature,
    )
    body = json.dumps({
        "model": model_id,
        "temperature": temperature,
        "max_tokens": 8,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    }).encode()

    url = f"{_GEMINI_OPENAI_URL}/chat/completions"
    req = urlrequest.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        text = data["choices"][0]["message"]["content"].strip().lower()
    except (urlerror.HTTPError, urlerror.URLError, KeyError) as exc:
        print(f"    API error: {exc}", file=sys.stderr)
        return "error"

    if "associated" in text:
        return "associated"
    return "unrelated"


def _self_consistency(
    *,
    model_id: str,
    api_key: str,
    sentence: str,
    microbe: str,
    feature: str,
    num_samples: int = 7,
) -> tuple[str, list[str]]:
    """Run self-consistency classification. Returns (final_label, sample_labels)."""
    temps = [round(0.45 + i * (0.85 - 0.45) / max(num_samples - 1, 1), 3)
             for i in range(num_samples)]

    labels: list[str] = []
    for t in temps:
        label = _call_gemini(
            model_id=model_id, api_key=api_key,
            sentence=sentence, microbe=microbe, feature=feature,
            temperature=t,
        )
        labels.append(label)
        time.sleep(0.15)  # rate-limit courtesy

    # Require full consistency
    if all(l == "associated" for l in labels):
        return "associated", labels
    return "unrelated", labels


# ── Candidate extraction ────────────────────────────────────────────

def _find_feature_in_text(text_lower: str) -> tuple[str, str] | None:
    """Returns (canonical, node_type) for first matching feature, or None."""
    for alias, canonical, node_type in _FEATURE_VOCAB:
        if alias in _ABBREV_ALIASES:
            # Word-boundary match for short abbreviations
            if re.search(rf"\b{re.escape(alias)}\b", text_lower):
                return canonical, node_type
        else:
            if alias in text_lower:
                return canonical, node_type
    return None


def _extract_candidates(
    entity_sentences_paths: list[Path],
) -> list[dict[str, Any]]:
    """Scan entity sentences for microbe + feature co-occurrences."""
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()  # (pmid, microbe, feature)

    for path in entity_sentences_paths:
        if not path.exists():
            print(f"  SKIP {path.name} (not found)")
            continue
        with open(path) as f:
            for line in f:
                r = json.loads(line)
                sentence = r.get("sentence", "")
                sentence_lower = sentence.lower()
                microbes = r.get("microbes", [])
                pmid = str(r.get("pmid", ""))

                if not microbes:
                    continue

                match = _find_feature_in_text(sentence_lower)
                if match is None:
                    continue
                canonical, node_type = match

                for m in microbes:
                    mtext = m["text"] if isinstance(m, dict) else str(m)
                    mtext_clean = mtext.strip().lower()

                    # Skip if microbe text IS the feature (NER sometimes tags features as microbes)
                    if mtext_clean == canonical.replace("_", " "):
                        continue

                    dedup_key = (pmid, mtext_clean, canonical)
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    candidates.append({
                        "pmid": pmid,
                        "microbe": mtext_clean,
                        "feature_canonical": canonical,
                        "feature_node_type": node_type,
                        "sentence": sentence,
                        "source_file": path.name,
                    })

    return candidates


# ── Main ────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entity-sentences", nargs="+",
        default=[
            "artifacts/entity_sentences_microbe_expanded.jsonl",
            "artifacts/entity_sentences_new_lanes.jsonl",
        ],
        help="Entity sentences JSONL files to scan",
    )
    parser.add_argument(
        "--model-id", default="gemini-2.5-flash-lite",
        help="Gemini model for classification",
    )
    parser.add_argument(
        "--num-samples", type=int, default=7,
        help="Self-consistency samples per candidate (default: 7)",
    )
    parser.add_argument(
        "--output", default="artifacts/microbe_feature_relations.jsonl",
        help="Output JSONL path",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show candidates without calling API",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key and not args.dry_run:
        print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
        return 1

    # Step 1: Extract candidates
    paths = [Path(p) for p in args.entity_sentences]
    print(f"[1/3] Scanning {len(paths)} entity sentence files for microbe + feature co-occurrences")
    candidates = _extract_candidates(paths)
    print(f"  Found {len(candidates)} unique (pmid, microbe, feature) candidates\n")

    if not candidates:
        print("No candidates found. Exiting.")
        return 0

    for c in candidates:
        print(f"  {c['microbe'][:30]:30s}  →  {c['feature_canonical']:25s}  PMID {c['pmid']}")
    print()

    if args.dry_run:
        print(f"Dry run — would classify {len(candidates)} candidates "
              f"({len(candidates) * args.num_samples} API calls)")
        return 0

    # Step 2: Self-consistency classification
    print(f"[2/3] Running Gemini self-consistency ({args.num_samples} samples each, "
          f"{len(candidates) * args.num_samples} total API calls)\n")

    accepted: list[dict[str, Any]] = []
    for i, c in enumerate(candidates, 1):
        label, samples = _self_consistency(
            model_id=args.model_id,
            api_key=api_key,
            sentence=c["sentence"],
            microbe=c["microbe"],
            feature=c["feature_canonical"].replace("_", " "),
            num_samples=args.num_samples,
        )
        tag = "[+]" if label == "associated" else "[-]"
        assoc_count = sum(1 for s in samples if s == "associated")
        print(f"  {tag} {i:2d}/{len(candidates)}  {c['microbe'][:25]:25s} → "
              f"{c['feature_canonical']:25s}  {assoc_count}/{len(samples)} associated")

        if label == "associated":
            record_id = hashlib.sha1(
                f"{c['pmid']}|{c['microbe']}|{c['feature_canonical']}".encode()
            ).hexdigest()[:16]
            accepted.append({
                "record_id": record_id,
                "pmid": c["pmid"],
                "source_node_type": "Microbe",
                "source_node": c["microbe"],
                "target_node_type": c["feature_node_type"],
                "target_node": c["feature_canonical"],
                "rel_type": "CORRELATES_WITH",
                "evidence": f"PMID {c['pmid']}: {c['sentence'][:250]}",
                "confidence": 1.0,
                "classification": label,
                "sample_labels": samples,
                "source_file": c["source_file"],
            })

    # Step 3: Write output
    print(f"\n[3/3] Results: {len(accepted)}/{len(candidates)} accepted\n")

    output_path = Path(args.output)
    with open(output_path, "w") as f:
        for rec in accepted:
            f.write(json.dumps(rec) + "\n")
    print(f"  Written to {output_path}")

    if accepted:
        print("\n  Accepted edges:")
        for rec in accepted:
            print(f"    {rec['source_node']} →[CORRELATES_WITH]→ {rec['target_node']}  (PMID {rec['pmid']})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
