import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from llmdev import bench, cards, registry, runner, server

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
        )

        print(json.dumps(meta))

        if meta["passed"]:
            return 0
        else:
            return 1

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

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if e.code is not None else 1

    try:
        return _dispatch(args)
    except (registry.RegistryError, server.ServerError, cards.CardError) as e:
        print(str(e), file=sys.stderr)
        return 1
