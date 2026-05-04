"""Unit tests for src/verify_vision_dual.py.

Tests use:
  - a stub pixel verifier (returns a dict, no actual image processing)
  - a stub HTTP poster (returns hand-crafted Gemini-shaped JSON)

This avoids loading numpy/Pillow image fixtures and avoids any live
Gemini API calls.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest

from src.verify_vision_dual import (
    ConsensusOutcome,
    PixelVerdict,
    VisionVerdict,
    VisionVerifierConfig,
    build_verifier_prompt,
    call_vision_verifier,
    consensus,
    dual_verify,
    pixel_verdict_from_payload,
    vision_verdict_from_payload,
)


# --------------------------------------------------------------------------- #
#  Pixel verdict translation
# --------------------------------------------------------------------------- #
def test_pixel_pass_when_verified():
    assert pixel_verdict_from_payload({"verified": True}) == PixelVerdict.PASS


def test_pixel_fail_when_unverified_with_hard_reason():
    assert pixel_verdict_from_payload({
        "verified": False, "reason_code": "insufficient_support"
    }) == PixelVerdict.FAIL


def test_pixel_inconclusive_for_legend_failures():
    assert pixel_verdict_from_payload({
        "verified": False, "reason_code": "legend_not_found"
    }) == PixelVerdict.INCONCLUSIVE


def test_pixel_inconclusive_for_pixel_starvation():
    assert pixel_verdict_from_payload({
        "verified": False, "reason_code": "insufficient_colored_pixels"
    }) == PixelVerdict.INCONCLUSIVE


def test_pixel_inconclusive_for_r_out_of_range():
    assert pixel_verdict_from_payload({
        "verified": False, "reason_code": "r_out_of_range"
    }) == PixelVerdict.INCONCLUSIVE


# --------------------------------------------------------------------------- #
#  Vision verdict translation
# --------------------------------------------------------------------------- #
def test_vision_pass():
    assert vision_verdict_from_payload({"verdict": "pass"}) == VisionVerdict.PASS


def test_vision_fail():
    assert vision_verdict_from_payload({"verdict": "fail"}) == VisionVerdict.FAIL


def test_vision_inconclusive():
    assert vision_verdict_from_payload({"verdict": "inconclusive"}) == VisionVerdict.INCONCLUSIVE


def test_vision_unknown_treated_as_inconclusive():
    assert vision_verdict_from_payload({}) == VisionVerdict.INCONCLUSIVE
    assert vision_verdict_from_payload({"verdict": "??"}) == VisionVerdict.INCONCLUSIVE


# --------------------------------------------------------------------------- #
#  Verifier prompt
# --------------------------------------------------------------------------- #
def test_verifier_prompt_contains_proposal_fields():
    proposal = {
        "topology": "heatmap",
        "subject": "Akkermansia muciniphila",
        "feature": "GLCM_Correlation",
        "value": 0.95,
        "value_min": -1.0,
        "value_max": 1.0,
    }
    system, user = build_verifier_prompt(proposal)
    assert "verification-only" in system.lower()
    assert "Akkermansia muciniphila" in user
    assert "GLCM_Correlation" in user
    assert "0.95" in user
    # Verifier-only constraint must be visible to the model
    assert "Do NOT propose" in user


def test_verifier_prompt_falls_back_to_alternate_fields():
    proposal = {"row_label": "Bacteroides", "column_label": "VAT", "r_value": -0.42}
    _, user = build_verifier_prompt(proposal)
    assert "Bacteroides" in user
    assert "VAT" in user
    assert "-0.42" in user


# --------------------------------------------------------------------------- #
#  Consensus gate
# --------------------------------------------------------------------------- #
def test_and_consensus_accepts():
    out = consensus(pixel=PixelVerdict.PASS, vision=VisionVerdict.PASS)
    assert out.accepted is True
    assert out.needs_review is False
    assert out.rationale == "both_verifiers_pass"


def test_both_fail_rejects_without_review():
    out = consensus(pixel=PixelVerdict.FAIL, vision=VisionVerdict.FAIL)
    assert out.accepted is False
    assert out.needs_review is False
    assert out.rationale == "both_verifiers_reject"


def test_xor_disagreement_routes_to_review():
    out = consensus(pixel=PixelVerdict.PASS, vision=VisionVerdict.FAIL)
    assert out.accepted is False
    assert out.needs_review is True
    assert "verifier_disagreement" in out.rationale


def test_pixel_inconclusive_vision_pass_routes_to_review():
    out = consensus(pixel=PixelVerdict.INCONCLUSIVE, vision=VisionVerdict.PASS)
    assert out.accepted is False
    assert out.needs_review is True


def test_both_inconclusive_routes_to_review():
    out = consensus(pixel=PixelVerdict.INCONCLUSIVE, vision=VisionVerdict.INCONCLUSIVE)
    assert out.accepted is False
    assert out.needs_review is True
    assert "inconclusive" in out.rationale


def test_consensus_payload_round_trip():
    out = consensus(
        pixel=PixelVerdict.PASS, vision=VisionVerdict.PASS,
        pixel_payload={"verified": True, "support_pixels": 42},
        vision_payload={"verdict": "pass", "confidence": 0.91},
    )
    d = out.as_dict()
    assert d["accepted"] is True
    assert d["pixel_verdict"] == "pixel_pass"
    assert d["vision_verdict"] == "vision_pass"
    assert d["pixel_payload"]["support_pixels"] == 42
    assert d["vision_payload"]["confidence"] == pytest.approx(0.91)


# --------------------------------------------------------------------------- #
#  Vision client with mock HTTP
# --------------------------------------------------------------------------- #
def _make_image(tmp_path: Path) -> Path:
    p = tmp_path / "fig.png"
    # 1×1 transparent PNG
    p.write_bytes(base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgYAAAAAMA"
        b"ASsJTYQAAAAASUVORK5CYII="
    ))
    return p


def _gemini_response_json(content: str) -> bytes:
    return json.dumps({"choices": [{"message": {"content": content}}]}).encode()


def test_call_vision_verifier_passes_proposal_in_request(tmp_path):
    seen: dict[str, Any] = {}

    def fake_post(url: str, headers: dict[str, str], body: bytes,
                  timeout: float) -> bytes:
        seen["url"] = url
        seen["headers"] = headers
        seen["body"] = json.loads(body.decode())
        seen["timeout"] = timeout
        return _gemini_response_json(json.dumps({
            "verdict": "pass",
            "observed_color_band": "deep red",
            "discrepancy": "none",
            "confidence": 0.92,
        }))

    image = _make_image(tmp_path)
    cfg = VisionVerifierConfig(
        api_base_url="https://example.test/v1beta/openai",
        model_id="gemini-2.5-flash",
        api_key="sk-test",
        temperature=0.0,
    )
    proposal = {"subject": "Akk", "feature": "VAT", "value": 0.81}
    payload = call_vision_verifier(
        image_path=str(image), proposal=proposal,
        config=cfg, http_post=fake_post,
    )
    assert payload["verdict"] == "pass"
    assert seen["url"].endswith("/chat/completions")
    assert seen["headers"]["Authorization"] == "Bearer sk-test"
    assert seen["body"]["temperature"] == 0.0
    assert seen["body"]["model"] == "gemini-2.5-flash"
    user_content = seen["body"]["messages"][1]["content"]
    assert any("Akk" in p.get("text", "") for p in user_content
               if p["type"] == "text")
    assert any(p["type"] == "image_url" for p in user_content)


def test_call_vision_verifier_handles_markdown_fenced_json(tmp_path):
    def fake_post(url, headers, body, timeout):
        return _gemini_response_json(
            "```json\n"
            '{"verdict": "fail", "discrepancy": "large", "confidence": 0.81}\n'
            "```"
        )

    image = _make_image(tmp_path)
    cfg = VisionVerifierConfig(api_base_url="https://example.test")
    payload = call_vision_verifier(
        image_path=str(image), proposal={"subject": "x", "feature": "y", "value": 0},
        config=cfg, http_post=fake_post,
    )
    assert payload["verdict"] == "fail"


def test_call_vision_verifier_inconclusive_on_garbage(tmp_path):
    def fake_post(url, headers, body, timeout):
        return _gemini_response_json("the model went on a tangent and produced no JSON")

    image = _make_image(tmp_path)
    cfg = VisionVerifierConfig(api_base_url="https://example.test")
    payload = call_vision_verifier(
        image_path=str(image), proposal={"subject": "x", "feature": "y", "value": 0},
        config=cfg, http_post=fake_post,
    )
    assert payload["verdict"] == "inconclusive"


def test_call_vision_verifier_handles_list_content(tmp_path):
    def fake_post(url, headers, body, timeout):
        return json.dumps({
            "choices": [{
                "message": {
                    "content": [
                        {"type": "text", "text": '{"verdict":"pass","confidence":0.9}'}
                    ]
                }
            }]
        }).encode()

    image = _make_image(tmp_path)
    cfg = VisionVerifierConfig(api_base_url="https://example.test")
    payload = call_vision_verifier(
        image_path=str(image), proposal={"subject": "a", "feature": "b", "value": 0.5},
        config=cfg, http_post=fake_post,
    )
    assert payload["verdict"] == "pass"


# --------------------------------------------------------------------------- #
#  End-to-end dual_verify
# --------------------------------------------------------------------------- #
def test_dual_verify_accepts_when_both_pass(tmp_path):
    image = _make_image(tmp_path)

    def stub_pixel(value, image_path, **kwargs):
        return {"verified": True, "reason_code": "verified", "support_pixels": 50}

    def fake_post(url, headers, body, timeout):
        return _gemini_response_json('{"verdict":"pass","confidence":0.95}')

    cfg = VisionVerifierConfig(api_base_url="https://example.test", api_key="k")
    out = dual_verify(
        image_path=str(image),
        proposal={"subject": "A", "feature": "F", "value": 0.7},
        pixel_verifier=stub_pixel,
        vision_config=cfg,
        http_post=fake_post,
    )
    assert isinstance(out, ConsensusOutcome)
    assert out.accepted is True
    assert out.pixel == PixelVerdict.PASS
    assert out.vision == VisionVerdict.PASS


def test_dual_verify_review_on_disagreement(tmp_path):
    image = _make_image(tmp_path)

    def stub_pixel(value, image_path, **kwargs):
        return {"verified": True}

    def fake_post(url, headers, body, timeout):
        return _gemini_response_json('{"verdict":"fail","confidence":0.88}')

    cfg = VisionVerifierConfig(api_base_url="https://example.test")
    out = dual_verify(
        image_path=str(image),
        proposal={"subject": "A", "feature": "F", "value": 0.7},
        pixel_verifier=stub_pixel, vision_config=cfg, http_post=fake_post,
    )
    assert out.accepted is False
    assert out.needs_review is True
    assert out.pixel == PixelVerdict.PASS
    assert out.vision == VisionVerdict.FAIL


def test_dual_verify_skips_vision_when_config_none(tmp_path):
    image = _make_image(tmp_path)

    def stub_pixel(value, image_path, **kwargs):
        return {"verified": True}

    out = dual_verify(
        image_path=str(image),
        proposal={"subject": "A", "feature": "F", "value": 0.5},
        pixel_verifier=stub_pixel, vision_config=None,
    )
    # Pixel passed; vision disabled (inconclusive). Routes to review.
    assert out.accepted is False
    assert out.needs_review is True
    assert out.vision == VisionVerdict.INCONCLUSIVE
    assert out.vision_payload.get("error") == "vision_verifier_disabled"


def test_dual_verify_passes_pixel_kwargs(tmp_path):
    image = _make_image(tmp_path)
    seen_kwargs: dict[str, Any] = {}

    def stub_pixel(value, image_path, **kwargs):
        seen_kwargs.update(kwargs)
        return {"verified": True}

    out = dual_verify(
        image_path=str(image),
        proposal={"subject": "A", "feature": "F", "value": 0.5},
        pixel_verifier=stub_pixel, vision_config=None,
        pixel_kwargs={"tolerance": 0.07, "min_support_pixels": 25},
    )
    assert seen_kwargs["tolerance"] == pytest.approx(0.07)
    assert seen_kwargs["min_support_pixels"] == 25
    assert out.pixel == PixelVerdict.PASS
