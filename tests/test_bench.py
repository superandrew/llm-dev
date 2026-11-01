import unittest
import json
from llmdev.bench import (
    WORDS, make_prompt, parse_sse, measure, run, _post
)


class TestMakePrompt(unittest.TestCase):
    def test_make_prompt_deterministic(self):
        prompt1 = make_prompt(10, seed=0)
        prompt2 = make_prompt(10, seed=0)
        self.assertEqual(prompt1, prompt2)

    def test_make_prompt_seed_offset(self):
        prompt1 = make_prompt(10, seed=0)
        prompt2 = make_prompt(10, seed=1)
        self.assertNotEqual(prompt1, prompt2)

    def test_make_prompt_words(self):
        prompt = make_prompt(5, seed=0)
        self.assertTrue(prompt.startswith("the be to of and"))
        self.assertIn("Summarise the text above in one sentence.", prompt)

    def test_make_prompt_wrap(self):
        prompt = make_prompt(100, seed=0)
        words = prompt.split()[:100]
        self.assertEqual(len(words), 100)


class TestParseSSE(unittest.TestCase):
    def test_parse_sse_str(self):
        lines = [
            "data: {\"test\": 1}",
            "data: [DONE]",
            "",
            "data: {\"test\": 2}",
        ]
        result = list(parse_sse(lines))
        self.assertEqual(result, [{"test": 1}, {"test": 2}])

    def test_parse_sse_bytes(self):
        lines = [
            b"data: {\"test\": 1}",
            b"data: [DONE]",
            b"",
            b"data: {\"test\": 2}",
        ]
        result = list(parse_sse(lines))
        self.assertEqual(result, [{"test": 1}, {"test": 2}])

    def test_parse_sse_skip_done(self):
        lines = ["data: [DONE]"]
        result = list(parse_sse(lines))
        self.assertEqual(result, [])

    def test_parse_sse_skip_blank(self):
        lines = ["data: "]
        result = list(parse_sse(lines))
        self.assertEqual(result, [])

    def test_parse_sse_skip_non_data(self):
        lines = [
            "id: 1",
            "data: {\"test\": 1}",
            "retry: 1000",
        ]
        result = list(parse_sse(lines))
        self.assertEqual(result, [{"test": 1}])


class TestMeasure(unittest.TestCase):
    def test_measure_with_usage(self):
        t0 = 0.0
        events = [
            (1.0, {"choices": [{"delta": {"content": "Hello"}}]}),
            (2.0, {"choices": [{"delta": {"content": " world"}}]}),
            (3.0, {"usage": {"prompt_tokens": 10, "completion_tokens": 2}}),
        ]
        result = measure(t0, events)
        self.assertEqual(result["ttft_s"], 1.0)
        self.assertEqual(result["completion_tokens"], 2)
        self.assertEqual(result["prompt_tokens"], 10)
        self.assertEqual(result["prefill_tps"], 10.0)
        self.assertEqual(result["decode_tps"], 1.0)

    def test_measure_without_usage(self):
        t0 = 0.0
        events = [
            (1.0, {"choices": [{"delta": {"content": "Hello"}}]}),
            (2.0, {"choices": [{"delta": {"content": " world"}}]}),
        ]
        result = measure(t0, events)
        self.assertEqual(result["ttft_s"], 1.0)
        self.assertEqual(result["completion_tokens"], 2)
        self.assertIsNone(result["prompt_tokens"])
        self.assertIsNone(result["prefill_tps"])
        self.assertEqual(result["decode_tps"], 1.0)

    def test_measure_no_content(self):
        t0 = 0.0
        events = [
            (1.0, {"choices": [{"delta": {}}]}),
            (2.0, {"usage": {"prompt_tokens": 10, "completion_tokens": 0}}),
        ]
        result = measure(t0, events)
        self.assertIsNone(result["ttft_s"])
        self.assertEqual(result["completion_tokens"], 0)
        self.assertEqual(result["prompt_tokens"], 10)
        self.assertIsNone(result["prefill_tps"])
        self.assertIsNone(result["decode_tps"])

    def test_measure_rounding(self):
        t0 = 0.0
        events = [
            (1.333, {"choices": [{"delta": {"content": "Hello"}}]}),
            (2.666, {"choices": [{"delta": {"content": " world"}}]}),
            (3.999, {"usage": {"prompt_tokens": 10, "completion_tokens": 2}}),
        ]
        result = measure(t0, events)
        self.assertEqual(result["ttft_s"], 1.33)
        self.assertEqual(result["decode_tps"], 0.75)


class TestRun(unittest.TestCase):
    def test_run_payload(self):
        class FakeModel:
            name = "test"
            backend = "test"
            model = "test-model"
            host = "127.0.0.1"
            port = 11434

        def fake_post(url, payload, timeout=600):
            self.assertEqual(url, "http://127.0.0.1:11434/v1/chat/completions")
            self.assertEqual(payload["model"], "test-model")
            self.assertEqual(payload["stream"], True)
            self.assertEqual(payload["stream_options"], {"include_usage": True})
            self.assertEqual(payload["max_tokens"], 128)
            self.assertEqual(payload["temperature"], 0)
            self.assertIn("content", payload["messages"][0])
            yield b'data: {"choices": [{"delta": {"content": "test"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 1}}\n'
            yield b'data: [DONE]\n'

        def fake_clock():
            yield 0.0
            yield 1.0
            yield 2.0

        clock_gen = fake_clock()
        result = run(FakeModel(), post=fake_post, clock=lambda: next(clock_gen))
        self.assertEqual(result["model"], "test")
        self.assertEqual(result["backend"], "test")
        self.assertEqual(result["n_words"], 2000)

    def test_run_with_clock_iterator(self):
        class FakeModel:
            name = "test"
            backend = "test"
            model = "test-model"
            host = "127.0.0.1"
            port = 11434

        def fake_post(url, payload, timeout=600):
            yield b'data: {"choices": [{"delta": {"content": "A"}}]}\n'
            yield b'data: {"choices": [{"delta": {"content": "B"}}]}\n'
            yield b'data: {"choices": [{"delta": {"content": "C"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 3}}\n'
            yield b'data: [DONE]\n'

        clock_times = [0.0, 1.0, 2.0, 3.0, 4.0]
        clock_iter = iter(clock_times)

        result = run(FakeModel(), post=fake_post, clock=lambda: next(clock_iter))
        self.assertEqual(result["ttft_s"], 1.0)
        self.assertEqual(result["completion_tokens"], 3)
        self.assertEqual(result["prompt_tokens"], 10)
        self.assertEqual(result["prefill_tps"], 10.0)
        self.assertEqual(result["decode_tps"], 1.0)


if __name__ == "__main__":
    unittest.main()
