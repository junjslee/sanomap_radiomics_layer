from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import read_jsonl, write_jsonl, write_manifest
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.verify_heatmap import verify_heatmap_r_value

DEFAULT_MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"
DEFAULT_PROMPT_ID = "qwen_heatmap_v1_json"


@dataclass
class ProposerOptions:
    backend: str
    model_id: str
    prompt_id: str
    api_base_url: str | None
    api_key: str | None
    temperature: float
    max_tokens: int
    allow_fallback: bool
    device: str = "cpu"


_QWEN_LOCAL_PIPE_CACHE: dict[tuple[str, str], Any] = {}


def _proposal_id(pmid: str, figure_id: str, panel_id: str) -> str:
    return hashlib.sha1(f"{pmid}|{figure_id}|{panel_id}".encode("utf-8")).hexdigest()[:16]


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_bbox(value: Any) -> list[int] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        keys = ["x", "y", "w", "h"]
        if all(k in value for k in keys):
            out = []
            for key in keys:
                try:
                    out.append(int(value[key]))
                except (TypeError, ValueError):
                    return None
            return out
        return None
    if isinstance(value, list) and len(value) == 4:
        out = []
        for elem in value:
            try:
                out.append(int(elem))
            except (TypeError, ValueError):
                return None
        return out
    return None


def _extract_first_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("empty_response")

    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("json_not_found")

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError("json_parse_failed") from exc

    if not isinstance(parsed, dict):
        raise ValueError("json_not_object")
    return parsed


def _build_prompt(caption: str) -> str:
    return (
        "Extract one numeric correlation coefficient from this heatmap figure. "
        "Return JSON only with keys: candidate_r, panel_id, bbox, legend_bbox, heatmap_bbox, modality, microbe, radiomic_feature, disease. "
        "candidate_r must be a number in [-1, 1]. "
        "bbox/legend_bbox/heatmap_bbox must be [x,y,w,h] or null. "
        f"Figure caption/context: {caption}"
    )


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


def _build_completion_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    return cleaned + "/chat/completions"


def _call_qwen_openai_compatible(
    *,
    image_path: str,
    caption: str,
    options: ProposerOptions,
) -> str:
    if not options.api_base_url:
        raise RuntimeError("missing_api_base_url")

    image_uri = _encode_image_data_uri(image_path)
    body = {
        "model": options.model_id,
        "temperature": options.temperature,
        "max_tokens": options.max_tokens,
        "messages": [
            {
                "role": "system",
                "content": "You are a medical figure parser. Output strict JSON only.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _build_prompt(caption)},
                    {"type": "image_url", "image_url": {"url": image_uri}},
                ],
            },
        ],
    }

    headers = {"Content-Type": "application/json"}
    if options.api_key:
        headers["Authorization"] = f"Bearer {options.api_key}"

    req = urlrequest.Request(
        _build_completion_url(options.api_base_url),
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urlerror.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        raise RuntimeError(f"http_error:{exc.code}:{detail}") from exc
    except urlerror.URLError as exc:
        raise RuntimeError(f"network_error:{exc.reason}") from exc

    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("missing_choices")

    message = choices[0].get("message", {})
    content = message.get("content")

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        return "\n".join(text_parts)
    raise RuntimeError("missing_message_content")


def _get_qwen_local_pipe(model_id: str, device: str) -> Any:
    key = (model_id, device)
    if key in _QWEN_LOCAL_PIPE_CACHE:
        return _QWEN_LOCAL_PIPE_CACHE[key]

    try:
        from transformers import pipeline  # type: ignore
    except Exception as exc:
        raise RuntimeError("transformers_not_available_for_qwen_local") from exc

    device_arg = -1
    if device.startswith("cuda"):
        device_arg = 0

    pipe = pipeline("image-text-to-text", model=model_id, device=device_arg)
    _QWEN_LOCAL_PIPE_CACHE[key] = pipe
    return pipe


def _coerce_local_output_text(output: Any) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            generated = first.get("generated_text")
            if isinstance(generated, str):
                return generated
            if isinstance(generated, list):
                text_parts: list[str] = []
                for item in generated:
                    if isinstance(item, dict):
                        content = item.get("content")
                        if isinstance(content, str):
                            text_parts.append(content)
                if text_parts:
                    return "\n".join(text_parts)
    if isinstance(output, dict):
        generated = output.get("generated_text")
        if isinstance(generated, str):
            return generated
    raise RuntimeError("qwen_local_unexpected_output_shape")


def _call_qwen_local(
    *,
    image_path: str,
    caption: str,
    options: ProposerOptions,
) -> str:
    pipe = _get_qwen_local_pipe(options.model_id, options.device)
    prompt = _build_prompt(caption)

    attempts: list[dict[str, Any]] = [
        {
            "images": image_path,
            "text": prompt,
            "max_new_tokens": options.max_tokens,
            "temperature": options.temperature,
            "do_sample": True,
        },
        {
            "inputs": {"image": image_path, "text": prompt},
            "max_new_tokens": options.max_tokens,
            "temperature": options.temperature,
            "do_sample": True,
        },
        {
            "inputs": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image_path},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_new_tokens": options.max_tokens,
            "temperature": options.temperature,
            "do_sample": True,
        },
    ]

    last_exc: Exception | None = None
    for kwargs in attempts:
        try:
            output = pipe(**kwargs)
            return _coerce_local_output_text(output)
        except Exception as exc:
            last_exc = exc
            continue

    raise RuntimeError(f"qwen_local_inference_failed:{last_exc}") from last_exc


def _parse_qwen_output(raw_response: str) -> dict[str, Any]:
    obj = _extract_first_json_object(raw_response)

    candidate_r = _coerce_float(
        obj.get("candidate_r", obj.get("proposed_r", obj.get("r_value", obj.get("r"))))
    )
    if candidate_r is not None:
        candidate_r = max(-1.0, min(1.0, candidate_r))

    panel_id = str(obj.get("panel_id") or "main")
    modality = obj.get("modality")
    if modality is not None:
        modality = str(modality)

    return {
        "candidate_r": candidate_r,
        "panel_id": panel_id,
        "bbox": _coerce_bbox(obj.get("bbox")),
        "legend_bbox": _coerce_bbox(obj.get("legend_bbox")),
        "heatmap_bbox": _coerce_bbox(obj.get("heatmap_bbox", obj.get("bbox"))),
        "modality": modality,
        "microbe": obj.get("microbe"),
        "subject_node_type": obj.get("subject_node_type"),
        "subject_node": obj.get("subject_node", obj.get("microbe")),
        "radiomic_feature": obj.get("radiomic_feature"),
        "disease": obj.get("disease"),
    }


def _heuristic_proposal(image_path: str) -> tuple[float | None, list[int] | None, str]:
    candidates = [round(-1.0 + 0.05 * i, 3) for i in range(41)]
    best_result: dict[str, Any] | None = None
    best_r: float | None = None
    best_score: tuple[float, float] | None = None

    for candidate in candidates:
        try:
            result = verify_heatmap_r_value(
                proposed_r=candidate,
                image_path=image_path,
                tolerance=0.06,
                min_support_pixels=15,
                min_support_fraction=0.0002,
            )
        except Exception as exc:
            payload = {"heuristic_error": str(exc)}
            return None, None, json.dumps(payload, ensure_ascii=True)

        support_fraction = float(result.get("support_fraction") or 0.0)
        min_abs_error = result.get("min_abs_error")
        distance = float(min_abs_error) if min_abs_error is not None else 9.0
        score = (support_fraction, -distance)

        if best_score is None or score > best_score:
            best_score = score
            best_result = result
            best_r = candidate

    if best_result is None:
        return None, None, json.dumps({"heuristic_error": "no_result"}, ensure_ascii=True)

    legend_bbox = best_result.get("legend_bbox")
    if not isinstance(legend_bbox, list) or len(legend_bbox) != 4:
        legend_bbox = None

    payload = {
        "method": "verify_heatmap_grid_search",
        "candidate_count": len(candidates),
        "best_result": best_result,
    }
    return best_r, legend_bbox, json.dumps(payload, ensure_ascii=True)


def _coerce_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _propose_for_figure(figure: dict[str, Any], options: ProposerOptions) -> dict[str, Any]:
    pmid = str(figure.get("pmid") or "")
    figure_id = str(figure.get("figure_id") or "")
    image_path = _coerce_str_or_none(figure.get("image_path"))
    caption = str(figure.get("caption") or "")
    panel_id = "main"

    base = {
        "proposal_id": _proposal_id(pmid, figure_id, panel_id),
        "pmid": pmid,
        "figure_id": figure_id,
        "panel_id": panel_id,
        "candidate_r": None,
        "proposed_r": None,
        "bbox": None,
        "legend_bbox": None,
        "heatmap_bbox": None,
        "modality": None,
        "prompt_id": options.prompt_id,
        "model_id": options.model_id,
        "raw_response": "",
        "status": "pending",
        "backend": options.backend,
        "image_path": image_path,
        "microbe": None,
        "subject_node_type": None,
        "subject_node": None,
        "radiomic_feature": None,
        "disease": None,
        "error": None,
    }

    if not image_path:
        base["status"] = "missing_image"
        base["error"] = "missing_image_path"
        return base

    if not Path(image_path).exists():
        base["status"] = "missing_image"
        base["error"] = "image_path_not_found"
        return base

    attempted_model = False

    if options.backend == "qwen_local":
        attempted_model = True
        try:
            raw_response = _call_qwen_local(
                image_path=image_path,
                caption=caption,
                options=options,
            )
            parsed = _parse_qwen_output(raw_response)
            base.update(parsed)
            base["raw_response"] = raw_response
            base["status"] = "ok"
            base["backend"] = "qwen_local"
            base["proposal_id"] = _proposal_id(pmid, figure_id, str(base.get("panel_id") or "main"))
            base["proposed_r"] = base["candidate_r"]
            return base
        except Exception as exc:
            base["error"] = str(exc)
            base["status"] = "model_error"

    if options.backend == "qwen_api":
        attempted_model = True
        try:
            raw_response = _call_qwen_openai_compatible(
                image_path=image_path,
                caption=caption,
                options=options,
            )
            parsed = _parse_qwen_output(raw_response)
            base.update(parsed)
            base["raw_response"] = raw_response
            base["status"] = "ok"
            base["backend"] = "qwen_api"
            base["proposal_id"] = _proposal_id(pmid, figure_id, str(base.get("panel_id") or "main"))
            base["proposed_r"] = base["candidate_r"]
            return base
        except Exception as exc:
            base["error"] = str(exc)
            base["status"] = "model_error"

    if options.backend == "auto":
        attempted_model = True
        local_error = None
        try:
            raw_response = _call_qwen_local(
                image_path=image_path,
                caption=caption,
                options=options,
            )
            parsed = _parse_qwen_output(raw_response)
            base.update(parsed)
            base["raw_response"] = raw_response
            base["status"] = "ok"
            base["backend"] = "qwen_local"
            base["proposal_id"] = _proposal_id(pmid, figure_id, str(base.get("panel_id") or "main"))
            base["proposed_r"] = base["candidate_r"]
            return base
        except Exception as exc:
            local_error = str(exc)

        if options.api_base_url:
            try:
                raw_response = _call_qwen_openai_compatible(
                    image_path=image_path,
                    caption=caption,
                    options=options,
                )
                parsed = _parse_qwen_output(raw_response)
                base.update(parsed)
                base["raw_response"] = raw_response
                base["status"] = "ok"
                base["backend"] = "qwen_api"
                base["proposal_id"] = _proposal_id(pmid, figure_id, str(base.get("panel_id") or "main"))
                base["proposed_r"] = base["candidate_r"]
                return base
            except Exception as exc:
                base["error"] = f"local={local_error};api={exc}"
                base["status"] = "model_error"
        else:
            base["error"] = local_error
            base["status"] = "model_error"

    if options.backend in {"auto", "heuristic", "qwen_api", "qwen_local"}:
        if attempted_model and not options.allow_fallback and options.backend in {"auto", "qwen_api", "qwen_local"}:
            return base

        candidate_r, legend_bbox, raw = _heuristic_proposal(image_path)
        base["candidate_r"] = candidate_r
        base["proposed_r"] = candidate_r
        base["legend_bbox"] = legend_bbox
        base["raw_response"] = raw
        base["status"] = "ok" if candidate_r is not None else "heuristic_error"
        if attempted_model and base.get("error"):
            base["status"] = "fallback_heuristic"
        base["backend"] = "heuristic"
        base["model_id"] = options.model_id if attempted_model else "deterministic_heuristic"
        return base

    if options.backend in {"qwen_api", "qwen_local"} and base["status"] == "model_error":
        return base

    base["status"] = "unsupported_backend"
    base["error"] = f"Unsupported backend: {options.backend}"
    return base


def run_proposer(
    *,
    figures: list[dict[str, Any]],
    options: ProposerOptions,
    min_topology_confidence: float,
    include_non_heatmap: bool,
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for fig in figures:
        topology = str(fig.get("topology") or "unknown")
        conf = float(fig.get("topology_confidence") or 0.0)

        if topology != "heatmap" and not include_non_heatmap:
            continue
        if conf < min_topology_confidence:
            continue

        proposal = _propose_for_figure(fig, options)
        outputs.append(proposal)
    return outputs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Qwen-based vision proposals for heatmap r-values."
    )
    parser.add_argument("--figures", default="artifacts/figures.jsonl")
    parser.add_argument("--output", default="artifacts/vision_proposals.jsonl")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")
    parser.add_argument("--backend", choices=["auto", "qwen_local", "qwen_api", "heuristic"], default="auto")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--prompt-id", default=DEFAULT_PROMPT_ID)
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("QWEN_API_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("QWEN_API_KEY") or os.environ.get("OPENAI_API_KEY") or "",
    )
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=180)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--disable-fallback", action="store_true")
    parser.add_argument("--min-topology-confidence", type=float, default=0.1)
    parser.add_argument("--include-non-heatmap", action="store_true")
    parser.add_argument("--validate-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    figures_path = Path(args.figures)
    figures = read_jsonl(figures_path) if figures_path.exists() else []

    options = ProposerOptions(
        backend=args.backend,
        model_id=args.model_id,
        prompt_id=args.prompt_id,
        api_base_url=(args.api_base_url or None),
        api_key=(args.api_key or None),
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        allow_fallback=not args.disable_fallback,
        device=args.device,
    )

    proposals = run_proposer(
        figures=figures,
        options=options,
        min_topology_confidence=args.min_topology_confidence,
        include_non_heatmap=args.include_non_heatmap,
    )

    if args.validate_schema:
        schema = load_schema("vision_proposals.schema.json")
        for idx, proposal in enumerate(proposals):
            try:
                validate_record(proposal, schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"vision_proposals[{idx}] invalid: {exc}") from exc

    count = write_jsonl(args.output, proposals)

    metrics = {
        "figures_in": len(figures),
        "proposals_out": count,
        "status_ok": sum(1 for p in proposals if p.get("status") == "ok"),
        "status_fallback_heuristic": sum(1 for p in proposals if p.get("status") == "fallback_heuristic"),
        "status_model_error": sum(1 for p in proposals if p.get("status") == "model_error"),
        "status_missing_image": sum(1 for p in proposals if p.get("status") == "missing_image"),
    }

    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="propose_vision_qwen",
        params={
            "figures": args.figures,
            "backend": args.backend,
            "model_id": args.model_id,
            "prompt_id": args.prompt_id,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "device": args.device,
            "fallback_enabled": not args.disable_fallback,
            "min_topology_confidence": args.min_topology_confidence,
            "include_non_heatmap": args.include_non_heatmap,
        },
        metrics=metrics,
        outputs={"vision_proposals": str(Path(args.output).resolve())},
        command=" ".join(sys.argv),
    )

    print(json.dumps({"output": args.output, "metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
