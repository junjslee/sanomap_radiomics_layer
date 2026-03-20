import unittest
from io import BytesIO
from unittest import mock
from urllib.error import HTTPError

from src.model_backends import (
    GEMINI_OPENAI_BASE_URL,
    NEGATIVE,
    POSITIVE,
    UNRELATED,
    OpenAICompatibleRelationBackend,
    build_minerva_prompt_messages,
    build_openai_completion_url,
    extract_openai_message_text,
    format_prompt_for_model,
    normalize_relation_label,
)


class TestModelBackends(unittest.TestCase):
    def test_build_openai_completion_url_appends_chat_completions(self) -> None:
        self.assertEqual(
            build_openai_completion_url("https://router.huggingface.co/v1"),
            "https://router.huggingface.co/v1/chat/completions",
        )
        self.assertEqual(
            build_openai_completion_url("http://localhost:11434/v1/chat/completions"),
            "http://localhost:11434/v1/chat/completions",
        )

    def test_extract_openai_message_text_handles_string_and_list_content(self) -> None:
        self.assertEqual(
            extract_openai_message_text(
                {"choices": [{"message": {"content": "positive"}}]}
            ),
            "positive",
        )
        self.assertEqual(
            extract_openai_message_text(
                {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"type": "text", "text": "negative"},
                                ]
                            }
                        }
                    ]
                }
            ),
            "negative",
        )

    def test_normalize_relation_label_handles_alternative_tokens(self) -> None:
        self.assertEqual(normalize_relation_label("a"), POSITIVE)
        self.assertEqual(normalize_relation_label("B"), NEGATIVE)
        self.assertEqual(normalize_relation_label("d"), UNRELATED)

    def test_minerva_prompt_builder(self) -> None:
        system, user = build_minerva_prompt_messages(
            sentence="Evidence sentence",
            microbe="E.coli",
            disease="diabetes",
        )
        self.assertIn("expert microbiologist", system)
        self.assertIn("Evidence sentence", user)
        self.assertIn("E.coli", user)
        self.assertIn("diabetes", user)

    def test_model_family_prompt_formatting(self) -> None:
        prompt = format_prompt_for_model(
            system="sys",
            user="usr",
            model_family="mixtral_8x7b_instruct",
        )
        self.assertIn("[INST]", prompt)
        self.assertIn("sys", prompt)
        self.assertIn("usr", prompt)

    def test_openai_compatible_backend_predicts_from_mocked_response(self) -> None:
        backend = OpenAICompatibleRelationBackend(
            model_id="BioMistral/BioMistral-7B",
            api_base_url="https://router.huggingface.co/v1",
            api_key="test-token",
        )

        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self) -> bytes:
                return b'{"choices":[{"message":{"content":"positive"}}]}'

        with mock.patch("src.model_backends.urlrequest.urlopen", return_value=FakeResponse()) as mocked_urlopen:
            label = backend.predict_relation(
                sentence="Lactobacillus increased in obesity.",
                microbe="Lactobacillus",
                disease="obesity",
                temperature=0.3,
                max_new_tokens=6,
            )

        self.assertEqual(label, POSITIVE)
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://router.huggingface.co/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")

    def test_openai_compatible_backend_retries_transient_http_error(self) -> None:
        backend = OpenAICompatibleRelationBackend(
            model_id="gemini-2.5-flash-lite",
            api_base_url=GEMINI_OPENAI_BASE_URL,
            api_key="test-token",
            max_retries=2,
            retry_backoff_seconds=0,
        )

        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self) -> bytes:
                return b'{"choices":[{"message":{"content":"negative"}}]}'

        transient_error = HTTPError(
            url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=BytesIO(
                b'{"error":{"code":503,"message":"high demand","status":"UNAVAILABLE"}}'
            ),
        )

        with mock.patch(
            "src.model_backends.urlrequest.urlopen",
            side_effect=[transient_error, FakeResponse()],
        ) as mocked_urlopen:
            label = backend.predict_relation(
                sentence="Lactobacillus increased in obesity.",
                microbe="Lactobacillus",
                disease="obesity",
                temperature=0.3,
                max_new_tokens=6,
            )

        self.assertEqual(label, NEGATIVE)
        self.assertEqual(mocked_urlopen.call_count, 2)

    def test_openai_compatible_backend_rejects_gemini_model_with_non_gemini_base_url(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "gemini models require api_base_url"):
            OpenAICompatibleRelationBackend(
                model_id="gemini-2.5-flash-lite",
                api_base_url="https://router.huggingface.co/v1",
                api_key="token",
            )

        backend = OpenAICompatibleRelationBackend(
            model_id="gemini-2.5-flash-lite",
            api_base_url=GEMINI_OPENAI_BASE_URL,
            api_key="token",
        )
        self.assertEqual(backend.api_base_url, GEMINI_OPENAI_BASE_URL)


if __name__ == "__main__":
    unittest.main()
