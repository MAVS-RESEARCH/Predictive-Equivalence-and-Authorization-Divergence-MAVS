# PEAD-Bench

PEAD-Bench is a causal research benchmark for testing whether prediction-facing state is sufficient to authorize an action and, independently, whether structured governance adds value when governance information is held equal.

The benchmark keeps two hypotheses separate:

- H1 tests information necessity using matched predictive states and divergent authorization states.
- H2 tests architectural value by comparing MAVS-GC with strong Raw-G methods under matched cases, evidence, budgets, and reporting.

Phase 0 freezes the research charter, claim boundaries, access-state dictionaries, diagnostic identities, method inventory, holdout custody contract, protected operating-point objective, and clause-level requirements registry.

Phase 1 implements the immutable record, canonical serialization, hashing, content identity, seed lineage, typed registry, run-layout, decision chronology, trace, and result-cleanup contracts. Neither phase generates benchmark cases, trains models, or reports scientific results.

## Phase 0 validation

Create an isolated environment and install the exact lock:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
```

Validate all frozen configuration:

```powershell
.\.venv\Scripts\python.exe scripts\validate_config.py --verify-sources
```

Run the Phase 0 compliance and mutation-stress audit:

```powershell
.\.venv\Scripts\python.exe scripts\audit_phase0.py --verify-sources --stress-iterations 1000
```

Run the independent unit and stress suites:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase0_tests.py
```

## Phase 1 verification

Validate the source identities, frozen study, and typed registries:

```powershell
.\.venv\Scripts\python.exe scripts\validate_config.py --study configs/study/pead_main_v1.yaml --verify-sources
```

Verify and confirm the initial manifest-bound result cleanup:

```powershell
.\.venv\Scripts\python.exe scripts\clear_results.py --scope pead --dry-run
.\.venv\Scripts\python.exe scripts\clear_results.py --scope pead --confirm
```

Run the complete regression, property, and stress suite and the Phase 1 audit:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase1_tests.py
.\.venv\Scripts\python.exe scripts\audit_phase1.py
```

All operational commands emit structured JSON console events. Each `console.log(...)` call is paired with a stable `STEP LOG` source comment and indexed by the applicable phase audit.

## Scientific boundaries

The project does not claim universal prediction insufficiency, universal MAVS optimality, deployment readiness, certification, or zero risk. Negative scientific outcomes are publishable when integrity gates pass. Integrity failures invalidate affected results.

See `WorkPlan.md` for the frozen implementation plan, `CLAIMS.md` for claim eligibility, and `Path.md` for the append-only execution ledger.
