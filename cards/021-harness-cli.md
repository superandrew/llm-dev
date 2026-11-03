+++
id = "021"
title = "Harness option for run and eval"
edit = ["llmdev/cli.py", "llmdev/evals.py", "tests/test_evals.py"]
read = ["AGENTS.md", "llmdev/runner.py", ".aider.model.settings.yml"]
checks = ["python3 -m unittest tests.test_evals -v", "python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/cli.py llmdev/evals.py", "git --no-pager diff --check HEAD"]
commit = "feat: llm run and llm eval take --harness"
edit_format = "diff"
+++

# 021 - Harness option for run and eval

`runner.run_card` takes `harness` (`"aider"`, `"qwen"` or `"opencode"`, listed in
`runner.HARNESSES`). Expose it on the command line and record it in the eval rows.

## llmdev/cli.py

1. On both the `run` and the `eval` parsers add:

        add_argument("--harness", choices=runner.HARNESSES, default="aider", help="Coding tool")

   (use `run_parser.add_argument(...)` and `eval_parser.add_argument(...)`).
2. In the `run` branch pass `harness=args.harness` to `runner.run_card`.
3. In the `eval` branch pass `harness=args.harness` to `evals.run_eval`.

## llmdev/evals.py

1. `run_eval` gets a new last parameter `harness="aider"` and passes `harness=harness` to `run_card`.
2. In the row dict, right after `"backend": m.backend,` add `"harness": harness,`.
3. In `format_evals`, the model cell becomes the model name followed by `+` and the harness
   when the row has a harness other than `"aider"`; rows without a harness show the model alone:

        model = fmt(row.get("model"))
        if row.get("harness", "aider") != "aider":
            model += "+" + row["harness"]

   and use `model` in place of `fmt(row.get("model"))` in `formatted_rows.append([...])`.

Nothing else changes.

## tests/test_evals.py

- In the existing test that uses `fake_run_card`, also check that the row has `"harness"` equal
  to `"aider"`.
- Add a test that calls `run_eval` the same way with `harness="qwen"` and checks that the fake
  `run_card` received `kwargs["harness"] == "qwen"` and the row has `"harness"` equal to `"qwen"`.
- `format_evals` of `[{"eval": "e", "model": "m", "backend": "mlx", "harness": "qwen"}]`
  contains `"m+qwen"`; of `[{"eval": "e", "model": "m", "backend": "mlx"}]` does not contain `"+"`.
