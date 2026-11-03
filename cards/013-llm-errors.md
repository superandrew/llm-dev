+++
id = "013"
title = "Record model errors"
edit = ["llmdev/runner.py", "llmdev/cli.py", "tests/test_runner.py"]
read = ["models.toml", "bin/llm", "AGENTS.md", "llmdev/cards.py", "llmdev/registry.py", "llmdev/server.py"]
checks = ["python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/runner.py llmdev/cli.py", "git --no-pager diff --check HEAD"]
commit = "feat: record model errors of a card run"
edit_format = "diff"
+++

# 013 - Record model errors

When the model server dies during a run (for example MLX with `metal::malloc`), Aider writes
the error in its history and the run looks like a model that wrote nothing. The runner reads
those lines from the history, so a broken server is not mistaken for a weak model.

## llmdev/runner.py

Add this function above `run_card`, exactly:

    LLM_ERROR_PREFIXES = ("litellm.", "Empty response received from LLM")

    def llm_errors(text: str) -> list:
        """Return the Aider history lines that report a model or server error."""
        errors = []
        for line in text.splitlines():
            if not line.startswith("> "):
                continue
            body = line[2:].strip()
            if body.startswith(LLM_ERROR_PREFIXES):
                errors.append(body)
        return errors

In `run_card`, after the checks, read `history_path` when it exists (UTF-8, `errors="replace"`)
and add the key `"llm_errors": llm_errors(text)` to `meta`; when the file does not exist the
value is `[]`. `passed` does not change.

## llmdev/cli.py

In the `run` command, after printing the meta JSON and before returning, when
`meta.get("llm_errors")` is not empty print to stderr `model errors: ` followed by the
first error. Nothing else changes.

## tests/test_runner.py

Add a class `TestLlmErrors`:

- The text `"> Tokens: 11k sent, 0 received.  \n> Empty response received from LLM. Check your provider account?  \n"`
  gives `["Empty response received from LLM. Check your provider account?"]`.
- The text `"> litellm.NotFoundError: NotFoundError: OpenAIException - Error code: 404 - {'error': 'generation thread died'}  \n"`
  gives a list of 1 item that starts with `"litellm.NotFoundError"`.
- The text `"litellm.NotFoundError at the start of a line without the marker\n"` gives `[]`.
- The text `"#### Implement card 011\n> Applied edit to llmdev/evals.py\n"` gives `[]`.
- An empty text gives `[]`.

In the existing `run_card` tests nothing changes, except that the meta they check may now
contain `llm_errors`.
