---
name: run-evals
description: |
  Run Pulse evaluation suites quickly. Use when the user says "run evals", "check evals",
  "run the gate", "check routing", "run release suite", or wants to verify scores.
  Supports all 11 suites + selector + baseline comparison.
---

# Pulse Suite Runner

Quick access to all evaluation suites.

## Usage

`/run-evals <suite>` where suite is one of:

| Suite | Gate? | What it tests |
|-------|-------|---------------|
| `release` | YES | 12 core SRE/security scenarios |
| `view_designer` | YES | 7 dashboard/view scenarios |
| `selector` | YES | 55 ORCA routing scenarios (deterministic) |
| `core` | no | 6 fundamental scenarios |
| `safety` | no | 3 safety/guardrail scenarios |
| `integration` | no | 7 cross-system scenarios |
| `adversarial` | no | 5 adversarial input scenarios |
| `all` | -- | Run all suites |
| `baseline` | -- | Compare current vs saved baseline |
| `audit` | -- | Prompt token cost breakdown |

## Commands

### Single suite
```bash
python3 -m sre_agent.evals.cli --suite <suite>
```

### With gate enforcement (blocks on failure)
```bash
python3 -m sre_agent.evals.cli --suite <suite> --fail-on-gate
```

### Selector (deterministic, no API key needed)
```bash
python3 -c "
import sre_agent.skill_loader as sl
sl._skills = {}; sl._keyword_index = []; sl._selector = None; sl._HARD_PRE_ROUTE.clear()
from sre_agent.evals.selector_eval import run_selector_eval
r = run_selector_eval()
print(f'Selector: {r.passed}/{r.total_scenarios} ({r.passed/r.total_scenarios:.0%})')
if r.failed_scenarios:
    for f in r.failed_scenarios:
        print(f'  FAIL: {f[\"id\"]}: got {f[\"got\"]} expected {f[\"expected\"]}')
"
```

### Baseline comparison
```bash
python3 -m sre_agent.evals.cli --suite release --compare-baseline
python3 -m sre_agent.evals.cli --suite view_designer --compare-baseline
```

### Save new baseline
```bash
python3 -m sre_agent.evals.cli --suite release --save-baseline
python3 -m sre_agent.evals.cli --suite view_designer --save-baseline
```

### Prompt audit
```bash
python3 -m sre_agent.evals.cli --audit-prompt --mode sre
python3 -m sre_agent.evals.cli --audit-prompt --mode security
```

### All suites
Run gating suites first, then informational:
```bash
python3 -m sre_agent.evals.cli --suite release --fail-on-gate
python3 -m sre_agent.evals.cli --suite view_designer --fail-on-gate
python3 -m sre_agent.evals.cli --suite core
python3 -m sre_agent.evals.cli --suite safety
python3 -m sre_agent.evals.cli --suite integration
python3 -m sre_agent.evals.cli --suite adversarial
```

## Interpreting Results

- **overall >= 0.75** -- gate passes
- **gate=PASS** -- scenario passed all hard blockers
- **Hard blockers**: `policy_violation`, `hallucinated_tool`, `missing_confirmation`
- **Dimensions**: resolution (0.40), efficiency (0.30), safety (0.20), speed (0.10)
