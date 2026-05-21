"""Dual-verifier consensus gate for Vision Track edges.

Combines two structurally independent verifiers:

  Verifier A (deterministic): pixel HSV analysis vs detected colorbar
                              legend, via ``verify_heatmap_r_value``.
  Verifier B (semantic VLM):  independent Gemini Vision call with a
                              verifier-only prompt and temperature 0.

A figure-derived edge is accepted only when both verifiers PASS
(AND-consensus). Disagreement (one PASS, one FAIL/INCONCLUSIVE) routes
to a review queue rather than silently rejecting — disagreement is
itself a calibration signal.

Design rationale (for the methods section):
    Single-modality verification is structurally vulnerable to
    correlated errors within the proposer + verifier pair (VLM
    monoculture). Self-consistency reduces *random* error but not
    systematic error — sampling the same model 7 times with different
    temperatures is correlated by construction. Convergent validity
    (Campbell & Fiske 1959) requires structurally distinct measurement
    modalities. Pixel HSV verification (deterministic, image-data-level)
    and semantic VLM verification (interpretive, language-level) have
    distinct failure modes: a brittle legend-bbox does not produce the
    same wrong answer as a hallucinated colour reading. Joint failure is
    bounded above by the product of marginal failure rates only under
    independence — which is partial here (both rely on image quality;
    Gemini's pretraining likely overlaps with PMC OA). Independence is
    therefore claimed at the modality level, not the data level, and
    documented as such in the limitations.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib import error as urlerror
from urllib import request as urlrequest


# --------------------------------------------------------------------------- #
#  Verdict enums + outcome
# --------------------------------------------------------------------------- #
class PixelVerdict(str, Enum):
    PASS = "pixel_pass"
    FAIL = "pixel_fail"
    INCONCLUSIVE = "pixel_inconclusive"


class VisionVerdict(str, Enum):
    PASS = "vision_pass"
    FAIL = "vision_fail"
    INCONCLUSIVE = "vision_inconclusive"


@dataclass
class ConsensusOutcome:
    accepted: bool
    needs_review: bool
    pixel: PixelVerdict
    vision: VisionVerdict
    rationale: str
    pixel_payload: dict[str, Any] = field(default_factory=dict)
    vision_payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "needs_review": self.needs_review,
            "pixel_verdict": self.pixel.value,
            "vision_verdict": self.vision.value,
            "rationale": self.rationale,
            "pixel_payload": self.pixel_payload,
            "vision_payload": self.vision_payload,
        }


# --------------------------------------------------------------------------- #
#  Pixel verdict from existing verifier
# --------------------------------------------------------------------------- #
def pixel_verdict_from_payload(payload: Mapping[str, Any]) -> PixelVerdict:
    """Translate ``verify_heatmap_r_value`` output into a PixelVerdict.

    The existing verifier returns ``{"verified": bool, "reason_code": str, ...}``.
    We treat ``verified=True`` as PASS, structural failures (legend not
    found, insufficient pixels) as INCONCLUSIVE rather than FAIL — the
    figure was unverifiable, not refuted.
    """
    if payload.get("verified"):
        return PixelVerdict.PASS
    reason = str(payload.get("reason_code") or payload.get("reason") or "")
    inconclusive_reasons = {
        "legend_not_found",
        "insufficient_colored_pixels",
        "r_out_of_range",
        "proposed_r_missing",
    }
    if reason in inconclusive_reasons:
        return PixelVerdict.INCONCLUSIVE
    return PixelVerdict.FAIL


# --------------------------------------------------------------------------- #
#  Verifier-only prompt
# --------------------------------------------------------------------------- #
VERIFIER_SYSTEM = (
    "You are a verification-only judge for biomedical heatmap readings. "
    "You will see ONE figure and ONE proposed reading. Your task is to "
    "assess whether the proposed reading is consistent with the figure. "
    "You MUST NOT propose new readings, propose alternative cells, or "
    "speculate beyond what the figure visibly shows. Reply with strict "
    "JSON only, no prose."
)

VERIFIER_USER_TEMPLATE = (
    "PROPOSED READING\n"
    "  Figure type: {topology}\n"
    "  Subject (row label): {subject}\n"
    "  Feature (column label): {feature}\n"
    "  Reported numerical value: {value}\n"
    "  Reported value range: {value_min} to {value_max}\n"
    "\n"
    "TASK\n"
    "  Inspect the cell at (row=\"{subject}\", column=\"{feature}\") of the "
    "figure. Compare its colour against the colourbar legend. Report whether "
    "the cell colour is CONSISTENT with the reported value.\n"
    "\n"
    "RULES\n"
    "  - If the cell is not clearly visible, reply \"inconclusive\".\n"
    "  - Do NOT propose alternative readings or correct the value.\n"
    "  - Do NOT extrapolate beyond the visible figure.\n"
    "\n"
    "OUTPUT (strict JSON, single object, no markdown)\n"
    "  {{\"verdict\": \"pass\" | \"fail\" | \"inconclusive\",\n"
    "    \"observed_color_band\": \"<2-5 word description>\",\n"
    "    \"discrepancy\": \"none\" | \"small\" | \"large\",\n"
    "    \"confidence\": <number in [0,1]>}}"
)


def build_verifier_prompt(proposal: Mapping[str, Any]) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the verifier call."""
    subject = str(proposal.get("subject") or proposal.get("row_label") or "")
    feature = str(proposal.get("feature") or proposal.get("column_label") or "")
    value = proposal.get("value")
    if value is None:
        value = proposal.get("r_value")
    topology = str(proposal.get("topology") or "heatmap")
    vmin = proposal.get("value_min", proposal.get("colorbar_min", -1.0))
    vmax = proposal.get("value_max", proposal.get("colorbar_max", 1.0))
    user = VERIFIER_USER_TEMPLATE.format(
        topology=topology,
        subject=subject,
        feature=feature,
        value=value,
        value_min=vmin,
        value_max=vmax,
    )
    return VERIFIER_SYSTEM, user


# --------------------------------------------------------------------------- #
#  Vision verifier client
# --------------------------------------------------------------------------- #
@dataclass
class VisionVerifierConfig:
    """Configuration for the independent Gemini Vision verifier call."""

    api_base_url: str
    model_id: str = "gemini-2.5-flash"
    api_key: str | None = None
    temperature: float = 0.0
    max_tokens: int = 256
    timeout_s: float = 120.0


# Pluggable HTTP client signature so tests can inject a mock.
HttpCaller = Callable[[str, dict[str, str], bytes, float], bytes]


def _default_http_post(url: str, headers: dict[str, str], body: bytes,
                       timeout: float) -> bytes:
    req = urlrequest.Request(url, data=body, headers=headers, method="POST")
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _encode_image_data_uri(image_path: str) -> str:
    path = Path(image_path)
    suffix = path.suffix.lower()
    mime = "image/png"
    if suffix in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif suffix == ".webp":
        mime = "image/webp"
    raw = path.read_bytes()
    data = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{data}"


def _completion_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    return cleaned + "/chat/completions"


def _parse_verifier_response(raw: str) -> dict[str, Any]:
    """Extract the first JSON object from the verifier response."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
    # Find the first balanced {...} block.
    start = text.find("{")
    if start < 0:
        return {"verdict": "inconclusive", "raw": raw}
    depth = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        return {"verdict": "inconclusive", "raw": raw}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {"verdict": "inconclusive", "raw": raw}


def call_vision_verifier(
    *,
    image_path: str,
    proposal: Mapping[str, Any],
    config: VisionVerifierConfig,
    http_post: HttpCaller | None = None,
) -> dict[str, Any]:
    """Issue the independent Gemini Vision verification call.

    Returns the parsed JSON dict. ``http_post`` defaults to urllib but is
    injectable for tests.
    """
    system_prompt, user_prompt = build_verifier_prompt(proposal)
    image_uri = _encode_image_data_uri(image_path)
    body = {
        "model": config.model_id,
        "temperature": float(config.temperature),
        "max_tokens": int(config.max_tokens),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_uri}},
            ]},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    poster = http_post or _default_http_post
    try:
        raw = poster(_completion_url(config.api_base_url), headers,
                     json.dumps(body).encode("utf-8"), config.timeout_s)
    except urlerror.HTTPError as exc:
        return {"verdict": "inconclusive",
                "error": f"http_error:{exc.code}"}
    except urlerror.URLError as exc:
        return {"verdict": "inconclusive",
                "error": f"network_error:{exc.reason}"}
    payload = json.loads(raw.decode("utf-8"))
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not choices:
        return {"verdict": "inconclusive", "error": "missing_choices"}
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        text = "\n".join(p.get("text", "") for p in content
                         if isinstance(p, dict) and p.get("type") == "text")
    else:
        text = str(content or "")
    return _parse_verifier_response(text)


def vision_verdict_from_payload(payload: Mapping[str, Any]) -> VisionVerdict:
    verdict = str(payload.get("verdict") or "inconclusive").lower()
    if verdict == "pass":
        return VisionVerdict.PASS
    if verdict == "fail":
        return VisionVerdict.FAIL
    return VisionVerdict.INCONCLUSIVE


# --------------------------------------------------------------------------- #
#  Consensus
# --------------------------------------------------------------------------- #
def consensus(
    *,
    pixel: PixelVerdict,
    vision: VisionVerdict,
    pixel_payload: Mapping[str, Any] | None = None,
    vision_payload: Mapping[str, Any] | None = None,
) -> ConsensusOutcome:
    """AND-consensus accept; XOR-disagreement → review queue."""
    pp = dict(pixel_payload or {})
    vp = dict(vision_payload or {})
    if pixel == PixelVerdict.PASS and vision == VisionVerdict.PASS:
        return ConsensusOutcome(
            accepted=True, needs_review=False,
            pixel=pixel, vision=vision,
            rationale="both_verifiers_pass",
            pixel_payload=pp, vision_payload=vp,
        )
    if pixel == PixelVerdict.FAIL and vision == VisionVerdict.FAIL:
        return ConsensusOutcome(
            accepted=False, needs_review=False,
            pixel=pixel, vision=vision,
            rationale="both_verifiers_reject",
            pixel_payload=pp, vision_payload=vp,
        )
    pixel_pass = pixel == PixelVerdict.PASS
    vision_pass = vision == VisionVerdict.PASS
    if pixel_pass != vision_pass and (pixel_pass or vision_pass):
        # XOR: exactly one passed → flag for human review
        return ConsensusOutcome(
            accepted=False, needs_review=True,
            pixel=pixel, vision=vision,
            rationale=f"verifier_disagreement:pixel={pixel.value},"
                      f"vision={vision.value}",
            pixel_payload=pp, vision_payload=vp,
        )
    # At least one inconclusive, neither passed → review queue
    return ConsensusOutcome(
        accepted=False, needs_review=True,
        pixel=pixel, vision=vision,
        rationale=f"inconclusive:pixel={pixel.value},vision={vision.value}",
        pixel_payload=pp, vision_payload=vp,
    )


# --------------------------------------------------------------------------- #
#  Top-level wrapper
# --------------------------------------------------------------------------- #
def dual_verify(
    *,
    image_path: str,
    proposal: Mapping[str, Any],
    pixel_verifier: Callable[..., dict[str, Any]],
    vision_config: VisionVerifierConfig | None,
    http_post: HttpCaller | None = None,
    pixel_kwargs: Mapping[str, Any] | None = None,
) -> ConsensusOutcome:
    """End-to-end dual verification for a single proposed edge.

    ``pixel_verifier`` should be ``src.verify_heatmap.verify_heatmap_r_value``
    or a compatible callable returning a dict with ``verified`` / ``reason_code``.
    """
    pixel_payload = pixel_verifier(
        proposal.get("value", proposal.get("r_value")),
        image_path,
        **dict(pixel_kwargs or {}),
    )
    pixel_v = pixel_verdict_from_payload(pixel_payload)

    if vision_config is None:
        vision_payload = {"verdict": "inconclusive",
                          "error": "vision_verifier_disabled"}
    else:
        vision_payload = call_vision_verifier(
            image_path=image_path, proposal=proposal,
            config=vision_config, http_post=http_post,
        )
    vision_v = vision_verdict_from_payload(vision_payload)
    return consensus(
        pixel=pixel_v, vision=vision_v,
        pixel_payload=pixel_payload, vision_payload=vision_payload,
    )


# --------------------------------------------------------------------------- #
#  CLI — live smoke test on existing proposals
# --------------------------------------------------------------------------- #
def _resolve_image_path(proposal: dict[str, Any], figures_dir: Path) -> Path | None:
    candidates = []
    for k in ("image_path", "panel_image_path", "figure_image_path"):
        v = proposal.get(k)
        if v:
            candidates.append(Path(str(v)))
    pmcid = proposal.get("pmcid")
    fig_id = proposal.get("figure_id")
    if pmcid and fig_id:
        candidates.append(figures_dir / f"{pmcid}_{fig_id}.png")
        candidates.append(figures_dir / f"{pmcid}_{fig_id}.jpg")
    for c in candidates:
        if c.exists():
            return c
    return None


def main(argv: list[str] | None = None) -> int:
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposals", required=True,
                        help="Vision proposals JSONL")
    parser.add_argument("--figures-dir", default="artifacts/figures",
                        help="Where to look up figure images")
    parser.add_argument("--output", required=True,
                        help="Dual-verification output JSONL")
    parser.add_argument("--review-queue",
                        default="artifacts/vision_review_queue.jsonl",
                        help="Path for verifier-disagreement records")
    parser.add_argument("--api-base-url",
                        default="https://generativelanguage.googleapis.com/v1beta/openai")
    parser.add_argument("--model-id", default="gemini-2.5-flash")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--pmcids", default="",
                        help="Comma-separated allow-list of PMCIDs to verify")
    parser.add_argument("--skip-vision", action="store_true",
                        help="Run pixel-only (consensus reduces to single gate)")
    args = parser.parse_args(argv)

    api_key = os.environ.get("GEMINI_API_KEY", "").strip() or None
    if not api_key and not args.skip_vision:
        print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
        return 1

    # Defer heavy import until CLI runs.
    from src.verify_heatmap import verify_heatmap_r_value

    config = None if args.skip_vision else VisionVerifierConfig(
        api_base_url=args.api_base_url,
        model_id=args.model_id,
        api_key=api_key,
        temperature=args.temperature,
    )
    figures_dir = Path(args.figures_dir)
    pmcid_filter: set[str] = {p.strip() for p in args.pmcids.split(",") if p.strip()}

    out_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    for line in Path(args.proposals).read_text().splitlines():
        if not line.strip():
            continue
        proposal = json.loads(line)
        pmcid = str(proposal.get("pmcid", ""))
        if pmcid_filter and pmcid not in pmcid_filter:
            continue
        image_path = _resolve_image_path(proposal, figures_dir)
        if image_path is None:
            print(f"  SKIP {pmcid}/{proposal.get('figure_id')}: image not found",
                  file=sys.stderr)
            continue
        outcome = dual_verify(
            image_path=str(image_path),
            proposal=proposal,
            pixel_verifier=verify_heatmap_r_value,
            vision_config=config,
        )
        row = {
            "pmcid": pmcid,
            "figure_id": proposal.get("figure_id"),
            "panel_id": proposal.get("panel_id"),
            "subject": proposal.get("subject"),
            "feature": proposal.get("feature"),
            "value": proposal.get("value", proposal.get("r_value")),
            **outcome.as_dict(),
        }
        out_rows.append(row)
        if outcome.needs_review:
            review_rows.append(row)
        verdict_tag = "ACCEPT" if outcome.accepted else (
            "REVIEW" if outcome.needs_review else "REJECT"
        )
        print(f"  {verdict_tag}  {pmcid}/{proposal.get('figure_id')}  "
              f"pixel={outcome.pixel.value}  vision={outcome.vision.value}")

    Path(args.output).write_text(
        "\n".join(json.dumps(r) for r in out_rows) + ("\n" if out_rows else "")
    )
    print(f"Wrote {len(out_rows)} dual-verification rows → {args.output}")
    if review_rows:
        Path(args.review_queue).write_text(
            "\n".join(json.dumps(r) for r in review_rows) + "\n"
        )
        print(f"Review queue: {len(review_rows)} → {args.review_queue}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PixelVerdict",
    "VisionVerdict",
    "ConsensusOutcome",
    "VisionVerifierConfig",
    "build_verifier_prompt",
    "pixel_verdict_from_payload",
    "vision_verdict_from_payload",
    "call_vision_verifier",
    "consensus",
    "dual_verify",
]
