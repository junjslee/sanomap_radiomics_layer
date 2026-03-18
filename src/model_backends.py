from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest


POSITIVE = "positive"
NEGATIVE = "negative"
UNRELATED = "unrelated"
GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


MODEL_FAMILY_MAP: dict[str, str] = {
    "biomistral_7b": "BioMistral/BioMistral-7B",
    "mistral_7b_instruct": "mistralai/Mistral-7B-Instruct-v0.1",
    "mixtral_8x7b_instruct": "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "zephyr_7b_beta": "HuggingFaceH4/zephyr-7b-beta",
}

MINERVA_TEMPLATE_GENERAL_INSTRUCTION = (
    "You are an expert microbiologist who given an excerpt from a research paper can easily "
    "identify the type of relation between a microbe and a disease. Doesn't create new information, "
    "but is completely faithful to the information provided, and always gives concise answers."
)
MINERVA_TEMPLATE_INSTRUCTION = (
    "Given the following meaning of the labels, answer the following question with the appropiate label.\n"
    "positive: This type is used to annotate microbe-disease entity pairs with positive correlation, "
    "such as microbe will cause or aggravate the disease, the microbe will increase when disease occurs.\n"
    "negative: This type is used to annotate microbe-disease entity pairs that have a negative correlation, "
    "such as microbe can be a treatment for a disease, or microbe will decrease when disease occurs.\n"
    "na: This type is used when the relation between a microbe and a disease is not clear from the context or there is no relation. "
    "In other words, use this label if the relation is not positive and not negative."
)
MINERVA_TEMPLATE_EVIDENCE = (
    "Based on the above description, evidence is as follows:\n"
    "{evidence}\n\n"
    "\"What is the relationship between {microbe} and {disease}?\n"
    "\""
)


def _build_minerva_system_user(*, sentence: str, microbe: str, disease: str) -> tuple[str, str]:
    system = MINERVA_TEMPLATE_GENERAL_INSTRUCTION + "\n" + MINERVA_TEMPLATE_INSTRUCTION
    user = MINERVA_TEMPLATE_EVIDENCE.format(
        evidence=sentence,
        microbe=microbe,
        disease=disease,
    )
    return system, user


def build_minerva_prompt_messages(*, sentence: str, microbe: str, disease: str) -> tuple[str, str]:
    return _build_minerva_system_user(sentence=sentence, microbe=microbe, disease=disease)


def _format_chat_prompt(*, system: str, user: str, model_family: str) -> str:
    fam = model_family.lower()

    # MINERVA's own pipeline merged system+user for Mistral-like models.
    if "mistral" in fam or "mixtral" in fam or "biomistral" in fam:
        merged = system + "\n" + user
        return f"<s>[INST] {merged} [/INST]"
    if "zephyr" in fam:
        return f"<|system|>\n{system}</s>\n<|user|>\n{user}</s>\n<|assistant|>\n"
    if "llama" in fam:
        return (
            "<|begin_of_text|>"
            "<|start_header_id|>system<|end_header_id|>\n"
            f"{system}<|eot_id|>"
            "<|start_header_id|>user<|end_header_id|>\n"
            f"{user}<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n"
        )

    return f"System: {system}\nUser: {user}\nAssistant:"


def format_prompt_for_model(*, system: str, user: str, model_family: str) -> str:
    return _format_chat_prompt(system=system, user=user, model_family=model_family)


def is_gemini_model_id(model_id: str | None) -> bool:
    if not model_id:
        return False
    base_model_id = model_id.split(":", 1)[0].strip().lower()
    return base_model_id.startswith("gemini-")


def is_gemini_openai_base_url(base_url: str | None) -> bool:
    if not base_url:
        return False
    return "generativelanguage.googleapis.com" in base_url.lower()


def build_openai_completion_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    return cleaned + "/chat/completions"


def extract_openai_message_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("missing_choices")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("invalid_choice_shape")

    message = first_choice.get("message", {})
    if not isinstance(message, dict):
        raise RuntimeError("invalid_message_shape")

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "text":
                continue
            text = item.get("text")
            if isinstance(text, str):
                text_parts.append(text)
        if text_parts:
            return "\n".join(text_parts)
    raise RuntimeError("missing_message_content")


def normalize_relation_label(text: str) -> str:
    normalized = text.strip().lower()
    first_line = normalized.splitlines()[0].strip() if normalized else ""
    first_token = first_line.split()[0].strip("()[]{}:;,.\"'") if first_line else ""

    alternatives = {
        "a": POSITIVE,
        "b": NEGATIVE,
        "c": UNRELATED,
        "d": UNRELATED,
    }
    if first_token in alternatives:
        return alternatives[first_token]

    if "positive" in normalized:
        return POSITIVE
    if "negative" in normalized:
        return NEGATIVE
    if first_token in {"na", "none", "unrelated", "relate", "related", "nan", "c", "d"}:
        return UNRELATED
    if normalized in {"na", "none", "unrelated", "relate", "related", "nan"}:
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


@dataclass
class OpenAICompatibleRelationBackend(BaseRelationBackend):
    model_id: str
    api_base_url: str
    api_key: str | None = None
    backend_name: str = "openai_compatible"

    def __post_init__(self) -> None:
        if is_gemini_model_id(self.model_id) and not is_gemini_openai_base_url(self.api_base_url):
            raise RuntimeError(
                "gemini models require api_base_url "
                f"{GEMINI_OPENAI_BASE_URL}"
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
        system, user = _build_minerva_system_user(
            sentence=sentence,
            microbe=microbe,
            disease=disease,
        )
        body = {
            "model": self.model_id,
            "temperature": temperature,
            "max_tokens": max_new_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = urlrequest.Request(
            build_openai_completion_url(self.api_base_url),
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urlerror.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(exc)
            raise RuntimeError(f"http_error:{exc.code}:{detail}") from exc
        except urlerror.URLError as exc:
            raise RuntimeError(f"network_error:{exc.reason}") from exc

        text = extract_openai_message_text(payload)
        return normalize_relation_label(text)


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
    model_family: str = "biomistral_7b"
    prompt_style: str = "minerva_upstream"
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
        if self.prompt_style == "minerva_upstream":
            system, user = _build_minerva_system_user(
                sentence=sentence,
                microbe=microbe,
                disease=disease,
            )
            return _format_chat_prompt(
                system=system,
                user=user,
                model_family=self.model_family,
            )

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
    api_base_url: str | None = None,
    api_key: str | None = None,
) -> BaseRelationBackend:
    if backend == "heuristic":
        return HeuristicRelationBackend()
    if backend == "hf_textgen":
        resolved = resolve_model_id(model_family, model_id)
        return HuggingFaceTextGenBackend(
            model_id=resolved,
            model_family=model_family,
            prompt_style="minerva_upstream",
            device=device,
        )
    if backend == "openai_compatible":
        if not api_base_url:
            raise RuntimeError("api_base_url is required for openai_compatible backend")
        resolved = resolve_model_id(model_family, model_id)
        return OpenAICompatibleRelationBackend(
            model_id=resolved,
            api_base_url=api_base_url,
            api_key=api_key,
        )
    raise ValueError(f"Unsupported backend: {backend}")


__all__ = [
    "POSITIVE",
    "NEGATIVE",
    "UNRELATED",
    "MODEL_FAMILY_MAP",
    "MINERVA_TEMPLATE_GENERAL_INSTRUCTION",
    "MINERVA_TEMPLATE_INSTRUCTION",
    "MINERVA_TEMPLATE_EVIDENCE",
    "build_minerva_prompt_messages",
    "format_prompt_for_model",
    "GEMINI_OPENAI_BASE_URL",
    "is_gemini_model_id",
    "is_gemini_openai_base_url",
    "build_openai_completion_url",
    "extract_openai_message_text",
    "BaseRelationBackend",
    "OpenAICompatibleRelationBackend",
    "HeuristicRelationBackend",
    "HuggingFaceTextGenBackend",
    "normalize_relation_label",
    "resolve_model_id",
    "build_backend",
]
