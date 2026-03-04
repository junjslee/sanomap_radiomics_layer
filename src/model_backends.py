from __future__ import annotations

from dataclasses import dataclass
from typing import Any


POSITIVE = "positive"
NEGATIVE = "negative"
UNRELATED = "unrelated"


MODEL_FAMILY_MAP: dict[str, str] = {
    "biomistral_7b": "BioMistral/BioMistral-7B",
    "mistral_7b_instruct": "mistralai/Mistral-7B-Instruct-v0.1",
    "mixtral_8x7b_instruct": "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "zephyr_7b_beta": "HuggingFaceH4/zephyr-7b-beta",
}


def normalize_relation_label(text: str) -> str:
    normalized = text.strip().lower()
    if "positive" in normalized:
        return POSITIVE
    if "negative" in normalized:
        return NEGATIVE
    if normalized in {"na", "none", "unrelated", "relate", "related"}:
        return UNRELATED
    return UNRELATED


class BaseRelationBackend:
    backend_name = "base"

    def predict_relation(
        self,
        *,
        sentence: str,
        microbe: str,
        disease: str,
        temperature: float = 0.7,
        max_new_tokens: int = 16,
    ) -> str:
        raise NotImplementedError


class HeuristicRelationBackend(BaseRelationBackend):
    backend_name = "heuristic"

    positive_markers = {
        "increase",
        "increased",
        "higher",
        "enriched",
        "associated with",
        "promotes",
        "elevated",
        "risk",
        "correlated",
        "positive",
    }
    negative_markers = {
        "decrease",
        "decreased",
        "lower",
        "reduced",
        "protective",
        "ameliorate",
        "inhibits",
        "negative",
        "inversely",
    }

    def predict_relation(
        self,
        *,
        sentence: str,
        microbe: str,
        disease: str,
        temperature: float = 0.7,
        max_new_tokens: int = 16,
    ) -> str:
        # temperature/max_new_tokens are accepted for interface compatibility.
        _ = temperature, max_new_tokens, microbe, disease
        text = sentence.lower()
        pos_hits = sum(1 for k in self.positive_markers if k in text)
        neg_hits = sum(1 for k in self.negative_markers if k in text)

        if pos_hits == 0 and neg_hits == 0:
            return UNRELATED
        if pos_hits > neg_hits:
            return POSITIVE
        if neg_hits > pos_hits:
            return NEGATIVE
        return UNRELATED


@dataclass
class HuggingFaceTextGenBackend(BaseRelationBackend):
    model_id: str
    device: str = "cpu"
    backend_name: str = "hf_textgen"

    def __post_init__(self) -> None:
        try:
            from transformers import pipeline  # type: ignore
        except ImportError as exc:
            raise RuntimeError("transformers is required for hf_textgen backend") from exc

        device_arg: int = -1
        if self.device.startswith("cuda"):
            device_arg = 0
        self._pipeline = pipeline(
            "text-generation",
            model=self.model_id,
            device=device_arg,
        )

    def _build_prompt(self, sentence: str, microbe: str, disease: str) -> str:
        return (
            "Given the sentence below, classify the relation between the microbe and disease as "
            "positive, negative, or unrelated. Return one label only.\n\n"
            f"Sentence: {sentence}\n"
            f"Microbe: {microbe}\n"
            f"Disease: {disease}\n"
            "Label:"
        )

    def predict_relation(
        self,
        *,
        sentence: str,
        microbe: str,
        disease: str,
        temperature: float = 0.7,
        max_new_tokens: int = 16,
    ) -> str:
        prompt = self._build_prompt(sentence, microbe, disease)
        output = self._pipeline(
            prompt,
            do_sample=True,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            return_full_text=False,
        )
        text = str(output[0].get("generated_text", ""))
        return normalize_relation_label(text)


def resolve_model_id(model_family: str, override_model_id: str | None = None) -> str:
    if override_model_id:
        return override_model_id
    if model_family in MODEL_FAMILY_MAP:
        return MODEL_FAMILY_MAP[model_family]
    return model_family


def build_backend(
    *,
    backend: str,
    model_family: str = "biomistral_7b",
    model_id: str | None = None,
    device: str = "cpu",
) -> BaseRelationBackend:
    if backend == "heuristic":
        return HeuristicRelationBackend()
    if backend == "hf_textgen":
        resolved = resolve_model_id(model_family, model_id)
        return HuggingFaceTextGenBackend(model_id=resolved, device=device)
    raise ValueError(f"Unsupported backend: {backend}")


__all__ = [
    "POSITIVE",
    "NEGATIVE",
    "UNRELATED",
    "MODEL_FAMILY_MAP",
    "BaseRelationBackend",
    "HeuristicRelationBackend",
    "HuggingFaceTextGenBackend",
    "normalize_relation_label",
    "resolve_model_id",
    "build_backend",
]
