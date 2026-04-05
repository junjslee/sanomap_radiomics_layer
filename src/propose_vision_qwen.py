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

DEFAULT_MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"
DEFAULT_PROMPT_ID = "qwen_heatmap_v2_json"


@dataclass
class ProposerOptions:
    backend: str
    model_id: str
    prompt_id: str
    api_base_url: str | None
    api_key: str | None
    temperature: float
    max_tokens: int
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


def _build_prompt_heatmap(caption: str) -> str:
    return (
        "You are analyzing a biomedical gradient correlation heatmap figure.\n\n"
        "Task:\n"
        "1. Identify which axis contains MICROBIAL TAXA (bacteria, fungi, or archaea — "
        "genus or species names such as Bacteroides, Prevotella nigrescens, Fusobacterium).\n"
        "2. Identify which axis contains RADIOMIC or IMAGING FEATURES (e.g., GLCM entropy, "
        "wavelet energy, first-order kurtosis, LAA%, wall thickness, liver fat fraction, "
        "skeletal muscle index, shape features).\n"
        "3. Find the cell with the highest absolute Pearson or Spearman r-value where one "
        "axis is a microbial taxon and the other is a radiomic/imaging feature.\n"
        "4. If the figure has multiple panels (A, B, etc.), process each panel and return "
        "the strongest microbe-feature correlation found.\n\n"
        "Return ONLY a single valid JSON object — no markdown, no explanation:\n"
        "{\n"
        '  "candidate_r": <number in [-1, 1], or null if no microbe-feature pair found>,\n'
        '  "effect_type": "correlation_r",\n'
        '  "ci_lower": null, "ci_upper": null, "p_value": null,\n'
        '  "panel_id": <"A", "B", "main", or other panel label>,\n'
        '  "microbe": <exact microbial taxon name COPIED from the axis label — do not abbreviate>,\n'
        '  "radiomic_feature": <exact feature name COPIED from the axis label — do not abbreviate>,\n'
        '  "disease": <disease mentioned in figure title or caption, or null>,\n'
        '  "modality": <imaging modality such as CT, MRI, DXA, PET, or null>,\n'
        '  "bbox": <[x,y,w,h] bounding box of the strongest cell, or null>,\n'
        '  "heatmap_bbox": <[x,y,w,h] of the heatmap matrix area excluding legend, or null>,\n'
        '  "legend_bbox": <[x,y,w,h] of the color scale gradient legend bar, or null>\n'
        "}\n\n"
        "IMPORTANT: Copy axis label text EXACTLY as it appears in the figure — do not "
        "paraphrase or abbreviate. If no microbial taxon is present on any axis, set "
        "candidate_r and microbe to null.\n\n"
        f"Figure caption: {caption}"
    )


def _build_prompt_forest(caption: str) -> str:
    return (
        "You are analyzing a biomedical forest plot figure.\n\n"
        "Task: Find the row where the subject is a MICROBIAL TAXON (bacteria/fungi/archaea — "
        "genus or species name) and the outcome is a RADIOMIC FEATURE, IMAGING PHENOTYPE, or DISEASE. "
        "If multiple such rows exist, return the one with the most extreme effect size (farthest from null).\n\n"
        "Return ONLY a single valid JSON object — no markdown, no explanation:\n"
        "{\n"
        '  "candidate_r": <center OR/HR/β value as a number, or null if no microbe row found>,\n'
        '  "effect_type": <"odds_ratio", "hazard_ratio", "beta_coefficient", or "correlation_r">,\n'
        '  "ci_lower": <lower bound of 95% CI as a number, or null>,\n'
        '  "ci_upper": <upper bound of 95% CI as a number, or null>,\n'
        '  "p_value": <p-value as a number, or null>,\n'
        '  "panel_id": <"A", "B", "main", etc.>,\n'
        '  "microbe": <exact microbial taxon COPIED from the row label — do not abbreviate>,\n'
        '  "radiomic_feature": <exact feature/phenotype COPIED from column/outcome label, or null>,\n'
        '  "disease": <disease outcome if the object is a disease, or null>,\n'
        '  "modality": <imaging modality or null>,\n'
        '  "bbox": null, "heatmap_bbox": null, "legend_bbox": null\n'
        "}\n\n"
        "IMPORTANT: For OR/HR, null value = 1.0. Copy all labels EXACTLY. "
        "If no microbial taxon is a subject in any row, set candidate_r and microbe to null.\n\n"
        f"Figure caption: {caption}"
    )


def _build_prompt_scatter(caption: str) -> str:
    return (
        "You are analyzing a biomedical scatter plot figure showing a correlation.\n\n"
        "Task:\n"
        "1. Identify whether one axis is a MICROBIAL TAXON (bacteria/fungi genus or species) "
        "and the other is a RADIOMIC or IMAGING FEATURE.\n"
        "2. Extract the annotated r-value or ρ-value (e.g., 'r = 0.65', 'ρ = -0.42') "
        "visible in the figure panel.\n"
        "3. If multiple panels, return the strongest microbe-feature correlation.\n\n"
        "Return ONLY a single valid JSON object — no markdown, no explanation:\n"
        "{\n"
        '  "candidate_r": <annotated r/ρ value in [-1, 1], or null if not found>,\n'
        '  "effect_type": "correlation_r",\n'
        '  "ci_lower": null, "ci_upper": null,\n'
        '  "p_value": <annotated p-value as number, or null>,\n'
        '  "panel_id": <"A", "B", "main", etc.>,\n'
        '  "microbe": <exact taxon name from axis label, or null>,\n'
        '  "radiomic_feature": <exact feature name from axis label, or null>,\n'
        '  "disease": <disease if applicable, or null>,\n'
        '  "modality": <CT, MRI, DXA, etc., or null>,\n'
        '  "bbox": null, "heatmap_bbox": null, "legend_bbox": null\n'
        "}\n\n"
        "IMPORTANT: Copy label text EXACTLY. If no r/ρ annotation is visible or no "
        "microbial taxon is on an axis, set candidate_r and microbe to null.\n\n"
        f"Figure caption: {caption}"
    )


def _build_prompt(caption: str, topology: str = "heatmap") -> str:
    if topology == "forest_plot":
        return _build_prompt_forest(caption)
    if topology in {"scatter_plot", "scatter"}:
        return _build_prompt_scatter(caption)
    # dot_plot and unknown fall back to heatmap-style extraction
    return _build_prompt_heatmap(caption)


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
    topology: str = "heatmap",
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
                    {"type": "text", "text": _build_prompt(caption, topology)},
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
    topology: str = "heatmap",
    options: ProposerOptions,
) -> str:
    pipe = _get_qwen_local_pipe(options.model_id, options.device)
    prompt = _build_prompt(caption, topology)

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
    # For correlation_r, clamp to [-1, 1]. For OR/HR, preserve the value unclamped.
    effect_type = str(obj.get("effect_type") or "correlation_r")
    if candidate_r is not None and effect_type == "correlation_r":
        candidate_r = max(-1.0, min(1.0, candidate_r))

    panel_id = str(obj.get("panel_id") or "main")
    modality = obj.get("modality")
    if modality is not None:
        modality = str(modality)

    ci_lower = _coerce_float(obj.get("ci_lower"))
    ci_upper = _coerce_float(obj.get("ci_upper"))
    p_value = _coerce_float(obj.get("p_value"))

    return {
        "candidate_r": candidate_r,
        "effect_type": effect_type,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "p_value": p_value,
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
    topology = str(figure.get("topology") or "heatmap")
    panel_id = "main"

    base = {
        "proposal_id": _proposal_id(pmid, figure_id, panel_id),
        "pmid": pmid,
        "figure_id": figure_id,
        "panel_id": panel_id,
        "topology": topology,
        "candidate_r": None,
        "effect_type": None,
        "ci_lower": None,
        "ci_upper": None,
        "p_value": None,
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

    if options.backend == "qwen_local":
        try:
            raw_response = _call_qwen_local(
                image_path=image_path,
                caption=caption,
                topology=topology,
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
        try:
            raw_response = _call_qwen_openai_compatible(
                image_path=image_path,
                caption=caption,
                topology=topology,
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
        local_error = None
        try:
            raw_response = _call_qwen_local(
                image_path=image_path,
                caption=caption,
                topology=topology,
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
                    topology=topology,
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

    if base["status"] == "model_error":
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
    # Topologies that the Vision Track can extract quantitative associations from.
    QUALIFYING_TOPOLOGIES = {"heatmap", "forest_plot", "scatter_plot", "dot_plot"}

    outputs: list[dict[str, Any]] = []
    for fig in figures:
        topology = str(fig.get("topology") or "unknown")
        conf = float(fig.get("topology_confidence") or 0.0)

        if topology not in QUALIFYING_TOPOLOGIES and not include_non_heatmap:
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
    parser.add_argument("--backend", choices=["auto", "qwen_local", "qwen_api"], default="auto")
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
