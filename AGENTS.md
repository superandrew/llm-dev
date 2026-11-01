# Rules for the local coding agent (Aider)

llm-dev is a deterministic toolkit to serve, benchmark and drive local LLMs
(Ollama, llama.cpp `llama-server`, MLX `mlx_lm.server`) on a Mac.

1. Work on exactly one card from `cards/`. Read it fully before editing.
   Edit only the files the card lists under `edit`.
2. Python >= 3.11, standard library only (tomllib, json, urllib, subprocess,
   dataclasses, argparse, unittest). No third-party imports anywhere.
3. Code that touches the outside world (processes, HTTP, clock, kill) takes the
   function as a parameter with the real one as default, so tests pass fakes.
   Tests never start processes, never open sockets, never sleep.
4. Never invent behaviour the card does not ask for. If something is unclear,
   write the question in `cards/QUESTIONS.md` and stop.
5. Small diffs: no reformatting, no renaming, no unrelated clean-up.
   No line may end with spaces. Use short SEARCH blocks.
6. Done means every command in the card's `checks` passes. The tests you write are
   yours to fix: when one of them fails, recompute its expected value by hand
   before changing the code. Never loop on the same failure: after two
   attempts, stop and write the question in `cards/QUESTIONS.md`.
7. Do not commit. Andrew commits after review with the card's `commit` message.
