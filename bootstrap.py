#!/usr/bin/env python3
"""Run one card with Aider until `llm run` exists (cards 004-005).
Usage: python3 bootstrap.py cards/001-registry.md [extra message]"""
import os, sys, tomllib

def front_matter(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    end = lines.index("+++", 1)
    return tomllib.loads("\n".join(lines[1:end]))

card_path = sys.argv[1]
c = front_matter(card_path)
os.makedirs("runs", exist_ok=True)
msg = (f"Implement card {c['id']} as written. Follow AGENTS.md. Edit only: "
       + ", ".join(c["edit"]) + ". Output SEARCH/REPLACE blocks now. "
       "No line may end with spaces. " + " ".join(sys.argv[2:]))
cmd = ["aider", "--model", "ollama_chat/qwen3-coder-next", "--no-auto-commits",
       "--no-gitignore", "--no-suggest-shell-commands", "--no-detect-urls",
       "--no-check-update", "--analytics-disable", "--no-show-model-warnings",
       "--map-tokens", "0", "--no-pretty", "--yes-always", "--timeout", "900",
       "--chat-history-file", f"runs/{c['id']}.md",
       "--read", "AGENTS.md", "--read", card_path]
for r in c.get("read", []):
    cmd += ["--read", r]
cmd += ["--test-cmd", " && ".join(c["checks"]), "--auto-test", "--message", msg]
cmd += c["edit"]
os.environ.setdefault("OLLAMA_API_BASE", "http://127.0.0.1:11434")
os.execvp(cmd[0], cmd)
