# PEAD-Bench

PEAD-Bench is a causal research benchmark for testing whether prediction-facing state is sufficient to authorize an action and, independently, whether structured governance adds value when governance information is held equal.

The benchmark keeps two hypotheses separate:

- H1 tests information necessity using matched predictive states and divergent authorization states.
- H2 tests architectural value by comparing MAVS-GC with strong Raw-G methods under matched cases, evidence, budgets, and reporting.

Phase 0 freezes the research charter, claim boundaries, access-state dictionaries, diagnostic identities, method inventory, holdout custody contract, protected operating-point objective, and clause-level requirements registry.

Phase 1 implements the immutable record, canonical serialization, hashing, content identity, seed lineage, typed registry, run-layout, decision chronology, trace, and result-cleanup contracts.

Phase 2 implements the independent authorization truth system: a strict declarative policy DSL, a total deterministic DSL evaluator, a separately coded procedural reference evaluator, exact compatible-world ambiguity certificates, released rule fixtures, and release-blocking agreement audits. These phases do not generate benchmark banks, train models, or report scientific results.

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

## Phase 2 verification

Run the complete regression, unit, property, metamorphic, and stress suite, then
execute the independent-label compliance audit:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase2_tests.py
.\.venv\Scripts\python.exe scripts\audit_labels.py
```

The retained Phase 2 evidence reports exact dual-engine agreement, per-stratum
Oracle rule accuracy, quarantine status, certificate completeness, evaluator
source independence, and later-phase boundary exclusions.

## Phase 3 verification

Phase 3 constructs the frozen exact and near validation banks in memory, verifies
independent primary/reference generation, enforces atomic lineage splits, checks
typed near distances, and tests authorization leakage. It does not release final
claim-bank rows; the signed Phase 9A allocation remains a mandatory release gate.

```powershell
.\.venv\Scripts\python.exe scripts\run_phase3_tests.py
.\.venv\Scripts\python.exe scripts\audit_equivalence.py
```

## Phase 4 verification

Phase 4 constructs governance-reversal sequences, frozen-registry diagnostic
scope banks, and exact compatible-world evidence-sufficiency proofs. It retains
validation evidence only; it does not train a scientific model, release a final
claim bank, or execute adaptive evidence acquisition.

```powershell
.\.venv\Scripts\python.exe scripts\run_phase4_tests.py
.\.venv\Scripts\python.exe scripts\audit_phase4.py
```

## Phase 5 verification

Phase 5 validates six open development-domain adapters against one universal
task, candidate, mechanism, projection, and validation contract. The D7/D8
development surface is restricted to placeholder identities and nonrevealing
shapes; concrete implementations remain custody-only for Phase 9A.

```powershell
.\.venv\Scripts\python.exe scripts\review_domains.py
.\.venv\Scripts\python.exe scripts\run_phase5_tests.py
.\.venv\Scripts\python.exe scripts\audit_phase5.py
```

## Scientific boundaries

The project does not claim universal prediction insufficiency, universal MAVS optimality, deployment readiness, certification, or zero risk. Negative scientific outcomes are publishable when integrity gates pass. Integrity failures invalidate affected results.

See `WorkPlan.md` for the frozen implementation plan, `CLAIMS.md` for claim eligibility, and `Path.md` for the append-only execution ledger.
