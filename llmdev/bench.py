import json
import time
import urllib.request
import urllib.error
from typing import Iterator

from llmdev.server import base_url

WORDS = (
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
    "or", "an", "will", "my", "one", "all", "would", "there", "their", "what",
    "so", "up", "out", "if", "about", "who", "get", "which", "go", "me"
)


def make_prompt(n_words: int, seed: int = 0) -> str:
    """Create a prompt with n_words words from WORDS starting at seed index."""
    words = []
    word_count = len(WORDS)
    start_index = seed % word_count
    for i in range(n_words):
        word_index = (start_index + i) % word_count
        words.append(WORDS[word_index])
    words_str = " ".join(words)
    return f"{words_str}\n\nSummarise the text above in one sentence."


def parse_sse(lines) -> Iterator[dict]:
    """Parse SSE lines, yielding JSON objects from data: lines."""
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        line = line.rstrip("\n\r")
        if line.startswith("data: "):
            payload = line[6:]
            if payload == "[DONE]" or payload.strip() == "":
                continue
            yield json.loads(payload)


def measure(t0: float, timed_events: list[tuple[float, dict]]) -> dict:
    """Measure timing metrics from timed events."""
    content_times = []
    completion_tokens = None
    prompt_tokens = None
    usage = None

    for _, event in timed_events:
        if "usage" in event:
            usage = event["usage"]
        choices = event.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            content = delta.get("content") or delta.get("reasoning_content") or delta.get("reasoning")
            if isinstance(content, str) and content:
                content_times.append(_)

    if usage:
        completion_tokens = usage.get("completion_tokens")
        prompt_tokens = usage.get("prompt_tokens")

    if completion_tokens is None:
        completion_tokens = len(content_times)

    ttft = None
    if content_times:
        ttft = content_times[0] - t0

    prefill_tps = None
    if ttft is not None and ttft > 0 and prompt_tokens is not None:
        prefill_tps = round(prompt_tokens / ttft, 2)

    ttft_s = round(ttft, 2) if ttft is not None else None

    decode_tps = None
    if len(content_times) > 1:
        decode_duration = content_times[-1] - content_times[0]
        if decode_duration > 0:
            decode_tps = round((completion_tokens - 1) / decode_duration, 2)

    return {
        "ttft_s": ttft_s,
        "completion_tokens": completion_tokens,
        "prompt_tokens": prompt_tokens,
        "prefill_tps": prefill_tps,
        "decode_tps": decode_tps,
    }


def _post(url: str, payload: dict, timeout: int = 600):
    """POST JSON to URL and yield response lines."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for line in resp:
            yield line


def run(
    m,
    n_words: int = 2000,
    max_tokens: int = 128,
    post=_post,
    clock=time.perf_counter,
    seed: int = 0,
) -> dict:
    """Run benchmark on model m."""
    prompt = make_prompt(n_words, seed)
    url = base_url(m) + "/chat/completions"
    payload = {
        "model": m.model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": max_tokens,
        "temperature": 0,
    }

    t0 = clock()
    timed_events = []

    for event in parse_sse(post(url, payload)):
        timed_events.append((clock(), event))

    result = measure(t0, timed_events)
    result["model"] = m.name
    result["backend"] = m.backend
    result["n_words"] = n_words

    return result
