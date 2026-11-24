# AI4Math — LLM-Powered Symbolic Mathematics & Proof System

**English** | **[简体中文](README.md)** | **[Showcase & Examples](examples/demo_showcase.md)**

**AI4Math** enables Large Language Models to perform exact symbolic computation, computer-assisted mathematical proofs, and publication-ready visualization via strict tool calling. Powered by a dual-engine architecture (**SymPy** + **SageMath**), it outputs clean, Obsidian-compatible **Markdown + LaTeX**.

---

## Highlights

- **Dual Symbolic Engines**:
  - **SymPy (In-Process)**: Fast calculus, linear algebra, polynomial rings, group axioms, and exact probability distributions, guarded by an AST & `__builtins__`-free expression sandbox.
  - **SageMath (Isolated Subprocess)**: Galois groups (including parallel Chebotarev statistical inference up to degree 30), number fields, elliptic curves, Groebner bases, lattices (Smith/Hermite/LLL), and arbitrary SageMath execution (`sage_eval`), running in credential-stripped process groups with hard timeouts.
- **Theory-First Preplanning & Theorem Advisor**:
  - Estimates computational scale before solving, matches domain theorem plugins (`ai4math/tools/theorems/*.json`), and structures complex problems into a `theorem -> invariants -> verification` pipeline instead of brute-force enumeration.
- **Proof Assistance**:
  - Built-in `construct_proof`, `verify_conjecture`, `explore_structure`, and `search_counterexample` tools for rigorous algebraic verification and counterexample hunting.
- **Mathematical Visualization**:
  - 10 plotting tools across **matplotlib** and **SageMath** (1D curves, parametric curves, implicit curves, inequality region intersections, 3D surfaces, and complex phase portraits).

---

## Tool Overview (57 Registered Tools)

| Category | Engine | Representative Tools |
|---|---|---|
| **Mathematical Analysis** | SymPy | `simplify_expression`, `differentiate`, `integrate`, `compute_limit`, `series_expansion`, `solve_equation`, `solve_ode`, `compute_sum`, `matrix_operation`, `step_by_step_simplify` |
| **Abstract Algebra** | SymPy | `polynomial_operation`, `named_group`, `permutation_operation`, `quotient_ring_operation`, `check_algebraic_structure`, `minimal_polynomial` |
| **Probability Theory** | SymPy | `distribution_info`, `compute_expectation`, `compute_variance`, `compute_probability`, `moment_generating_function`, `characteristic_function`, `bayes_theorem`, `covariance_correlation` |
| **Advanced Algebra & Number Theory** | SageMath | `finite_field_polynomial`, `groebner_basis`, `ideal_membership`, `number_field_info`, `galois_group`, `galois_group_chebotarev`, `elliptic_curve_info`, `advanced_group_theory`, `lattice_operation`, `number_theory_operation` |
| **Analysis, Combinatorics & General** | SageMath | `sage_integrate`, `sage_simplify`, `combinatorics_operation`, `sage_eval` |
| **Proof Support** | SageMath | `construct_proof`, `verify_conjecture`, `explore_structure`, `search_counterexample` |
| **Visualization** | Matplotlib / Sage | `plot_function`, `plot_parametric`, `plot_implicit`, `plot_inequality_region`, `plot_3d`, `sage_plot`, `sage_implicit_plot`, `sage_region_plot`, `sage_plot_3d`, `sage_complex_plot` |
| **Planning & Advisor** | Built-in | `theorem_advisor` + Domain Theorem Plugins |

---

## Quick Start

### 1. Installation

```bash
conda activate ai4math
pip install -e .
```

### 2. Configuration

```bash
cp .env.example .env
chmod 600 .env
# Edit .env and set OPENAI_API_KEY
```

Compatible with any OpenAI-compatible endpoint:
- **DeepSeek V4 (Default, Strict Tool Calling)**: `OPENAI_BASE_URL=https://api.deepseek.com/beta`
- **DeepSeek Standard**: `OPENAI_BASE_URL=https://api.deepseek.com`
- **Local vLLM / Ollama**: `OPENAI_BASE_URL=http://localhost:8000/v1` (when `AI4MATH_MODEL` is set alone, routing and preplanning automatically inherit that model)

### 3. Usage

```bash
# Interactive REPL
ai4math

# One-shot question
ai4math "Compute the Galois group of x^4 - 2 over Q"

# Read question from file & save Markdown response
ai4math -f question.md -o result.md

# Parallel batch mode with per-question hard timeout (separated by standalone --- lines)
ai4math -b examples/demo_questions.md -w 3 --timeout 180 -o output/demo_batch
```

### 4. Showcase Demo (Computation + Proof + Visualization)

Explore [`examples/`](examples/README.md) or view the pre-generated showcase report [`examples/demo_showcase.md`](examples/demo_showcase.md):

```bash
# Run deterministic engine showcase (no API key required)
python examples/run_demo.py

# Run end-to-end LLM showcase
python examples/run_demo.py --llm
```

---

## Project Structure

```text
ai4math/
├── .github/workflows/ci.yml     # GitHub Actions CI test pipeline
├── ai4math/
│   ├── cli.py                   # Interactive REPL & multiprocessing batch runner
│   ├── llm/client.py            # Tool-calling loop, auto-routing & preplanning
│   └── tools/
│       ├── _shared.py           # AST-validated SymPy parser & shared helpers
│       ├── registry.py          # Strict JSON Schema generator & tool dispatcher
│       ├── analysis.py          # Calculus, ODEs, series & matrices (SymPy)
│       ├── algebra.py           # Rings, groups & permutations (SymPy)
│       ├── probability.py       # Distributions, moments & probabilities (SymPy)
│       ├── plotting.py          # Matplotlib visualization tools
│       ├── theorem_advisor.py   # Scale estimation & domain theorem matching
│       ├── theorems/*.json      # Modular domain theorem knowledge plugins
│       ├── sage_tools.py        # Advanced algebra, number theory & proof tools
│       ├── sage_plotting.py     # SageMath 2D/3D/complex plotting tools
│       └── sage_subprocess.py   # Credential-stripped subprocess group runner
├── examples/                    # Runnable computation, proof & plotting demos
├── scripts/                     # Reference benchmark & research Sage scripts
├── tests/                       # Unit, security & 34-case regression test suites
├── README.md                    # Main Chinese documentation
└── README_EN.md                 # English documentation
```

---

## Security Notes

- **Execution Boundary**: Power tools such as `sage_eval`, `construct_proof`, `verify_conjecture`, `explore_structure`, and `search_counterexample` execute LLM-generated SageMath/Python code in local subprocesses under the current OS user account (not an OS container sandbox). **Do not run untrusted problem files (`-f` / `-b`) or load untrusted external theorem URLs.**
- **Built-in Hardening**:
  - Subprocesses automatically strip `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `*_API_KEY` / `*_SECRET` / `*_TOKEN` environment variables.
  - In-process SymPy parsing uses a `__builtins__`-free namespace and AST whitelist blocking private/dunder attribute traversal.
  - `DOT_SAGE` fallback directories are isolated per UID with `0700` permissions and symlink/ownership checks.
  - External theorem URLs require `https://` and enforce a 2 MiB size limit.

---

## Testing

```bash
python -m unittest \
  tests.test_theorem_advisor_external \
  tests.test_preplanning \
  tests.test_sage_subprocess \
  tests.test_tools_regression -v

python scripts/eval_solutions.py
```

---

## Citation

If AI4Math is helpful in your research or notes workflow, you may cite it as:

```bibtex
@software{ai4math2026,
  author       = {Euler2023},
  title        = {AI4Math: LLM-Powered Symbolic Mathematics, Proof Assistance, and Visualization System},
  year         = {2026},
  version      = {0.2.6},
  url          = {https://github.com/Euler2023/ai4math}
}
```
