import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

from system.llm import client
from system.llm.config import LLMSettings
from system.llm.errors import LLMError


def models(name):
    return NS(data=[NS(id=name)])


def response():
    return NS(
        model=None, choices=[NS(message=NS(content="answer"), finish_reason="stop")]
    )


async def chunks():
    yield NS(choices=[NS(delta=NS(content="answer"), finish_reason="stop")])


class ModelDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.settings = LLMSettings(
            env={
                "LLM_BASE_URL": "http://local.test/v1/",
                "LLM_MODEL": "obsolete-model",
            }
        )
        self.settings_patch = patch.object(
            client, "get_settings", return_value=self.settings
        )
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)

    def test_sync_rediscovers_model_before_each_request(self):
        self.assertIsNone(self.settings.model)
        sdk = Mock()
        sdk.models.list.side_effect = [models("first"), models("replacement")]
        sdk.chat.completions.create.return_value = response()
        with patch.object(client, "get_client", return_value=sdk):
            self.assertEqual(client.chat(prompt="hello").model, "first")
            self.assertEqual(client.chat(prompt="hello").model, "replacement")
        self.assertEqual(
            [c[0] for c in sdk.mock_calls],
            [
                "models.list",
                "chat.completions.create",
                "models.list",
                "chat.completions.create",
            ],
        )
        self.assertEqual(
            [c.kwargs["model"] for c in sdk.chat.completions.create.call_args_list],
            ["first", "replacement"],
        )

    def test_explicit_model_does_not_discover(self):
        sdk = Mock()
        sdk.chat.completions.create.return_value = response()
        with patch.object(client, "get_client", return_value=sdk):
            result = client.chat(
                prompt="hello", base_url="https://other.test/v1", model="chosen"
            )
        sdk.models.list.assert_not_called()
        self.assertEqual(result.model, "chosen")

    def test_empty_model_list_fails_without_completion(self):
        sdk = Mock()
        sdk.models.list.return_value = NS(data=[])
        with patch.object(client, "get_client", return_value=sdk):
            with self.assertRaises(LLMError):
                client.chat(prompt="hello")
        sdk.chat.completions.create.assert_not_called()

    def test_discovery_failure_uses_configured_fallback(self):
        settings = LLMSettings(
            env={
                "LLM_BASE_URL": "http://local.test/v1",
                "LLM_FALLBACK_BASE_URL": "https://backup.test/v1",
                "LLM_FALLBACK_API_KEY": "test-key",
                "LLM_FALLBACK_MODEL": "backup-model",
            }
        )
        local, backup = Mock(), Mock()
        local.models.list.side_effect = RuntimeError("unavailable")
        backup.chat.completions.create.return_value = response()
        with (
            patch.object(client, "get_settings", return_value=settings),
            patch.object(client, "get_client", side_effect=[local, backup]),
        ):
            result = client.chat(prompt="hello")
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.model, "backup-model")
        backup.models.list.assert_not_called()


class AsyncModelDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_and_stream_rediscovers_model(self):
        settings = LLMSettings(env={"LLM_BASE_URL": "http://local.test/v1"})
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                sdk = Mock()
                sdk.models.list = AsyncMock(
                    side_effect=[models("first"), models("replacement")]
                )
                sdk.chat.completions.create = AsyncMock(
                    side_effect=(lambda **kw: chunks()) if streaming else None,
                    return_value=response(),
                )
                with (
                    patch.object(client, "get_settings", return_value=settings),
                    patch.object(client, "get_async_client", return_value=sdk),
                ):
                    for expected_model in ("first", "replacement"):
                        if streaming:
                            self.assertEqual(
                                [part async for part in client.astream(prompt="hello")],
                                ["answer"],
                            )
                        else:
                            self.assertEqual(
                                (await client.achat(prompt="hello")).model,
                                expected_model,
                            )
                self.assertEqual(sdk.models.list.await_count, 2)
                self.assertEqual(
                    [
                        c.kwargs["model"]
                        for c in sdk.chat.completions.create.call_args_list
                    ],
                    ["first", "replacement"],
                )
                self.assertEqual(
                    [c[0] for c in sdk.mock_calls],
                    [
                        "models.list",
                        "chat.completions.create",
                        "models.list",
                        "chat.completions.create",
                    ],
                )


if __name__ == "__main__":
    unittest.main()
