import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from llmdev import bench, cards, evals, lab, metrics, registry, runner, server, pull

ROOT = Path(__file__).resolve().parent.parent


def _dispatch(args) -> int:
    models_path = ROOT / "models.toml"
    state_dir = ROOT / "state"
    runs_dir = ROOT / "runs"

    registry_data = registry.load(str(models_path))

    if args.command == "list":
        for name, model in sorted(registry_data.items()):
            print(f"{name} {model.backend} {model.model} {model.ctx} {model.port}")

    elif args.command == "serve":
        m = registry.get(registry_data, args.name)
        pid = server.start(m, str(state_dir))
        if pid is None:
            url = server.base_url(m)
            print(f"already serving at {url}")
        else:
            print(f"started pid {pid}")

    elif args.command == "stop":
        m = registry.get(registry_data, args.name)
        if server.stop(m, str(state_dir)):
            print("stopped")
        else:
            print("not running")

    elif args.command == "status":
        name = args.name
        if name is not None:
            m = registry.get(registry_data, name)
            result = server.status(m, str(state_dir))
            print(json.dumps([result]))
        else:
            results = []
            for name, m in sorted(registry_data.items()):
                results.append(server.status(m, str(state_dir)))
            print(json.dumps(results))

    elif args.command == "bench":
        m = registry.get(registry_data, args.name)
        if not server.health(m):
            print(f"{m.name} is not healthy", file=sys.stderr)
            return 1

        results = []
        for _ in range(args.repeat):
            result = bench.run(m, n_words=args.words, max_tokens=args.max_tokens)
            results.append(result)

        timestamp = datetime.now().isoformat()
        bench_path = ROOT / "runs" / "bench.jsonl"
        bench_path.parent.mkdir(parents=True, exist_ok=True)
        with open(bench_path, "a") as f:
            for result in results:
                result["timestamp"] = timestamp
                f.write(json.dumps(result) + "\n")

        print(json.dumps(results))

    elif args.command == "run":
        m = registry.get(registry_data, args.model)
        if not server.health(m):
            print(f"{m.name} is not healthy", file=sys.stderr)
            return 1

        card = cards.parse(args.card)

        base_url_str = server.base_url(m)
        meta = runner.run_card(
            card,
            m,
            base_url_str,
            args.repo,
            str(runs_dir),
            extra=args.message or "",
            timeout_s=args.timeout,
        )

        print(json.dumps(meta))

        if meta.get("llm_errors"):
            print(f"model errors: {meta['llm_errors'][0]}", file=sys.stderr)

        if meta["passed"]:
            return 0
        else:
            return 1

    elif args.command == "add":
        models_path = str(ROOT / "models.toml")
        block = pull.add_model(
            models_path,
            registry_data,
            args.name,
            args.backend,
            source=args.source,
            file=args.file or "",
            ctx=args.ctx,
        )
        print(block, end="")
        return 0

    elif args.command == "pull":
        m = registry.get(registry_data, args.name)
        returncode = pull.pull(m)
        if returncode == 0:
            print(f"pulled {args.name}")
            return 0
        else:
            print(f"pull failed with code {returncode}", file=sys.stderr)
            return returncode

    elif args.command == "sweep":
        m = registry.get(registry_data, args.name)
        if not server.health(m):
            print(f"{m.name} is not healthy", file=sys.stderr)
            return 1

        seed = int(datetime.now().timestamp()) % 50
        sweep_id = datetime.now().isoformat()

        try:
            rows = lab.sweep(m, seed=seed)
        except (TimeoutError, OSError) as e:
            print(f"sweep failed on {args.name}: {e}", file=sys.stderr)
            return 1

        for row in rows:
            row["sweep"] = sweep_id

        bench_path = ROOT / "runs" / "bench.jsonl"
        bench_path.parent.mkdir(parents=True, exist_ok=True)
        with open(bench_path, "a") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")

        summaries = lab.latest_sweeps(lab.read_rows(str(bench_path)))
        print(lab.format_table(summaries))
        return 0

    elif args.command == "results":
        bench_path = ROOT / "runs" / "bench.jsonl"
        rows = lab.read_rows(str(bench_path))
        summaries = lab.latest_sweeps(rows)
        print(lab.format_table(summaries))
        return 0

    elif args.command == "runs":
        rows = metrics.read_runs(str(runs_dir))
        if args.card:
            rows = [r for r in rows if r.get("card") == args.card]
        if args.model:
            rows = [r for r in rows if r.get("model") == args.model]
        print(metrics.format_runs(rows))
        return 0

    elif args.command == "tui":
        from llmdev import tui
        return tui.run_tui(str(ROOT))

    elif args.command == "eval":
        m = registry.get(registry_data, args.model)
        if not server.health(m):
            print(f"{m.name} is not healthy", file=sys.stderr)
            return 1

        runs_dir = ROOT / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        try:
            row = evals.run_eval(args.name, m, server.base_url(m), str(ROOT), str(runs_dir), timeout_s=args.timeout)
        except cards.CardError as e:
            print(str(e), file=sys.stderr)
            return 1

        evals_path = ROOT / "runs" / "eval.jsonl"
        evals_path.parent.mkdir(parents=True, exist_ok=True)
        with open(evals_path, "a") as f:
            f.write(json.dumps(row) + "\n")

        print(evals.format_evals([row]))

        if row.get("passed") and row.get("hidden_passed") == row.get("hidden_total") and row.get("hidden_total", 0) > 0:
            return 0
        return 1

    elif args.command == "evals":
        evals_path = ROOT / "runs" / "eval.jsonl"
        rows = evals.read_evals(str(evals_path))
        print(evals.format_evals(rows))
        return 0

    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="llm", description="llm command line")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    list_parser = subparsers.add_parser("list", help="List models")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start model server")
    serve_parser.add_argument("name", help="Model name")

    # stop
    stop_parser = subparsers.add_parser("stop", help="Stop model server")
    stop_parser.add_argument("name", help="Model name")

    # status
    status_parser = subparsers.add_parser("status", help="Show server status")
    status_parser.add_argument("name", nargs="?", help="Model name (optional)")

    # bench
    bench_parser = subparsers.add_parser("bench", help="Benchmark model")
    bench_parser.add_argument("name", help="Model name")
    bench_parser.add_argument("--words", type=int, default=2000, help="Number of words")
    bench_parser.add_argument("--max-tokens", type=int, default=128, help="Max tokens")
    bench_parser.add_argument("--repeat", type=int, default=2, help="Repeat count")

    # run
    run_parser = subparsers.add_parser("run", help="Run a card")
    run_parser.add_argument("card", help="Card file path")
    run_parser.add_argument("--model", required=True, help="Model name")
    run_parser.add_argument("--repo", default=".", help="Repository path")
    run_parser.add_argument("--message", help="Extra message")
    run_parser.add_argument("--timeout", type=int, default=2400, help="Timeout in seconds")

    # add
    add_parser = subparsers.add_parser("add", help="Add a model")
    add_parser.add_argument("name", help="Model name")
    add_parser.add_argument("--backend", required=True, choices=["ollama", "llama", "mlx"], help="Backend")
    add_parser.add_argument("--source", default="", help="Source (e.g., Hugging Face repo)")
    add_parser.add_argument("--file", default="", help="GGUF file name (for llama backend)")
    add_parser.add_argument("--ctx", type=int, default=65536, help="Context size")

    # pull
    pull_parser = subparsers.add_parser("pull", help="Pull a model")
    pull_parser.add_argument("name", help="Model name")

    # sweep
    sweep_parser = subparsers.add_parser("sweep", help="Run sweep benchmark")
    sweep_parser.add_argument("name", help="Model name")

    # results
    results_parser = subparsers.add_parser("results", help="Show sweep results")

    # runs
    runs_parser = subparsers.add_parser("runs", help="Show run records")
    runs_parser.add_argument("--card", help="Filter by card ID")
    runs_parser.add_argument("--model", help="Filter by model name")

    # tui
    subparsers.add_parser("tui", help="Open the lab TUI")

    # eval
    eval_parser = subparsers.add_parser("eval", help="Run an eval")
    eval_parser.add_argument("name", help="Eval name")
    eval_parser.add_argument("--model", required=True, help="Model name")
    eval_parser.add_argument("--timeout", type=int, default=1800, help="Timeout in seconds")

    # evals
    evals_parser = subparsers.add_parser("evals", help="Show eval records")

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if e.code is not None else 1

    try:
        return _dispatch(args)
    except (registry.RegistryError, server.ServerError, cards.CardError, pull.PullError) as e:
        print(str(e), file=sys.stderr)
        return 1
