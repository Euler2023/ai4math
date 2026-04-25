# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

### Install / run
- Install in editable mode: `pip install -e .`
- Start interactive CLI: `ai4math`
- One-shot question: `ai4math "化简 sin(x)^2 + cos(x)^2"`
- Read question from file: `ai4math -f question.md`
- Pipe input: `echo "求导 x^3" | ai4math`
- Save output to file: `ai4math -o result.md "问题"`

### Tests
- Run all currently maintained unit tests for planning / theorem loading: `python -m unittest tests.test_theorem_advisor_external tests.test_preplanning`
- Run only preplanning tests: `python -m unittest tests.test_preplanning`
- Run only theorem-advisor tests: `python -m unittest tests.test_theorem_advisor_external`
- Run a single unittest case: `python -m unittest tests.test_preplanning.TestPreplanning.test_heavy_scale_forces_theory_first_constraint`
- Run Sage subprocess tests: `python -m unittest tests.test_sage_subprocess`

## High-level architecture

### Entry flow
- CLI entrypoint is `ai4math.cli:main` from `pyproject.toml`.
- `ai4math/cli.py` is the operational hub for interactive mode, one-shot mode, file input, stdin mode, and batch mode.
- Tool modules are imported at CLI startup for side-effect registration. If a tool module is not imported, its tools will not be available.

### Solver pipeline
- Main orchestration lives in `ai4math/llm/client.py`.
- The pipeline is:
  1. `analyze_problem()` from `ai4math.tools.theorem_advisor`
  2. preplanning JSON generation
  3. inject preplan context as a system message
  4. tool-calling loop
  5. Markdown post-processing for final output
- Complex problems are intentionally routed through a structured workflow: `theorem -> invariants -> verification`.
- For heavy / infeasible problems, the preplan context explicitly forbids brute force and tries to force theory-first reasoning.

### Tool system
- Tool registration is implemented in `ai4math/tools/registry.py` via `@math_tool`.
- The registry auto-generates strict OpenAI-compatible JSON Schema from function signatures and docstrings.
- Important constraint: all declared tool parameters become required in the generated schema, and `additionalProperties` is `False`. Avoid casually adding optional metadata parameters to many tools.
- Non-Sage tools run in-process; categories whose name starts with `sage` run in an isolated subprocess through `ai4math/tools/sage_subprocess.py`.

### Theorem advisor and domain plugins
- The theorem knowledge base lives under `ai4math/tools/theorems/`.
- Builtin theorem data is split into multiple domain JSON files (for example algebraic geometry, number theory, combinatorics, elliptic curves). `theorems.json` remains as a backward-compatible aggregate.
- `ai4math/tools/theorem_advisor.py` auto-discovers and merges `tools/theorems/*.json`, then optionally merges an external theorem file or URL based on environment variables.
- Each theorem entry can contribute:
  - matching signals (`keywords`, `signals`)
  - planning hints (`prerequisites`, `invariant_hints`)
  - final-check hints (`verification_hints`)
- The maintainer schema for theorem entries is documented in `ai4math/tools/theorems/_schema.md`.

### Tests worth understanding before editing
- `tests/test_preplanning.py`: verifies planner output, heavy-problem constraints, and injected system context.
- `tests/test_theorem_advisor_external.py`: verifies builtin/external theorem loading, merge/dedup behavior, and structured theorem-advisor output.
- `tests/test_sage_subprocess.py`: verifies registry dispatch, Sage timeout handling, and recovery after killed subprocesses.

## Repository-specific maintenance rules

- When you change README changelog entries or user-visible release notes, also check `pyproject.toml` version and keep them in sync.
- When you change theorem/plugin architecture, update all of these together when relevant:
  - `README.md`
  - `ai4math/tools/theorems/_schema.md`
  - `pyproject.toml` package-data entries
  - tests covering theorem loading / preplanning
- When adding or moving theorem files under `ai4math/tools/theorems/`, preserve auto-discovery compatibility and avoid duplicate theorem `id` values across files.
- Prefer extending the theorem/preplanning data flow before changing tool signatures, because the strict registry schema makes broad tool-argument changes expensive.
