# PEAD-Bench Implementation Work Plan

Version: 1.0-plan
Plan date: 2026-07-30
Repository: `MAVS-RESEARCH/Predictive-Equivalence-and-Authorization-Divergence-MAVS`
Base commit: `9e6c1a7113f416c83aec4110c399273a2ded8b9b`
Normative specification: `PEAD_Benchmark_Implementation_Specification_v1.0.docx`
Scientific context: `MAVS-Diagnostic Sciences.pdf`

## 1. Purpose and non-negotiable contract

This plan converts the PEAD-Bench implementation specification into an executable, falsifiable, and audit-complete program. PEAD-Bench will construct decision worlds in which prediction-facing support is fixed while authorization-relevant evidence varies. It will test two separate hypotheses:

1. **H1 - information necessity:** whether prediction-facing state alone is sufficient to determine `Accept`, `Reject`, or `Escalate`.
2. **H2 - architecture value:** whether, after raw governance information is held equal, structured MAVS-GC governance provides a pre-registered advantage over strong flat or generic Raw-G methods.

H1 may pass while H2 fails. A MAVS win cannot rescue a failed or invalid H1 test. A scientifically negative result is retained and reported when integrity passes. An integrity failure invalidates the affected run.

The implementation will preserve the MAVS paper's central distinction:

> Prediction estimates support. Governance determines whether the available evidence authorizes action.

It will also preserve the Diagnostic Sciences requirements that each diagnostic has a declared scope, intended response, permitted influence path, and tests for in-scope value, out-of-scope influence, redundancy, instability, and composition.

### 1.1 Hard release gates

No headline claim is eligible unless all applicable gates pass:

- `PEI == 1.000000` for released exact pairs.
- `ADI == 1.000000` for released authorization-divergent exact pairs.
- Dual authorization-label agreement equals `1.000000`.
- Trace completeness equals `1.000000`.
- Access compliance equals `1.000000`.
- Deterministic artifact reproduction equals `1.000000`; explicitly registered tolerance rules apply only to nondeterministic model outputs.
- Holdout contamination, result-retention, budget-parity, abstention-degeneracy, and claim-eligibility audits pass.
- No generator, truth engine, or benchmark label code imports MAVS implementation code.
- Every claim-bearing number links to immutable decision traces, configuration hashes, code identity, and passing audits.

### 1.2 Scientific outcome is not a release gate

- If H1 fails with intact integrity, release a valid negative result.
- If H1 passes and H2 fails, conclude only that governance information matters on the registered PEAD class; do not claim MAVS architectural superiority.
- If a method achieves low unsafe acceptance through near-total rejection or escalation, report the coverage collapse; do not call it a safety success.
- Zero observed unsafe acceptance is finite-sample evidence, not certification.
- Self-Learning MAVS is excluded from the primary PEAD study. An adaptive-perception companion study may later use the reducibly ambiguous bank, but cannot rescue Paper 1.

## 2. Work discipline

### 2.1 `WorkPlan.md`

This file freezes phase scope, deliverables, implementation method, tests, commands, acceptance gates, model-training rules, claim boundaries, and phase dependencies. Any change after the study freeze creates a new study version.

### 2.2 `Path.md`

`Path.md` is the append-only execution ledger. Every meaningful implementation action must record:

- timestamp, phase, and change ID;
- files added, changed, removed, or generated;
- implementation details and commands;
- tests, benchmark runs, and exact artifact locations;
- pass/fail/invalid status with evidence;
- deviations from this plan and their scientific effect;
- failures, quarantines, corrections, and invalidated run IDs;
- result-cleaning operations and their exact scope;
- next permitted action.

A phase is not complete because code exists. It is complete only when its tests, stress runs, audits, retained evidence, and `Path.md` entries exist. A later defect reopens the affected phase and every dependent artifact.

### 2.3 Result hygiene

Generated results are never source code and are never silently reused.

- All new runs use immutable content-derived run IDs.
- A run directory is never overwritten. A rerun receives a new run ID and a parent/invalidation pointer.
- `scripts/clear_results.py` may remove only generated paths declared in a manifest and only after resolving and proving that every target is under `results/`.
- The cleanup command supports `--dry-run`, requires an explicit scope or run ID, rejects repository-root or unresolved targets, and writes a cleanup receipt to `Path.md` or a referenced artifact.
- Before the first PEAD run, pre-existing result artifacts must be inventoried and cleared. At plan creation, the remote repository contained only `LICENSE`; therefore the initial cleanup is a verified no-op.
- Development smoke artifacts are stored under named run IDs and are not carried into calibration, freeze, blind evaluation, or release.

### 2.4 Mandatory GitHub publication after every phase

Every phase must be committed and pushed to the GitHub repository automatically after its local completion gates pass. A phase is not complete, and work may not advance to the next phase, until its remote publication is verified.

The phase-close sequence is:

1. Finish the phase's implementation, tests, stress runs, audits, and evidence artifacts.
2. Update `Path.md` with the exact files, commands, test outcomes, run IDs, deviations, and phase-gate verdict.
3. Inspect `git status` and the complete intended diff; do not stage unrelated files.
4. Run `git diff --check` and all phase-required validation commands.
5. Commit the phase with a scoped message such as `phase-N: <completed scope>`.
6. Push the current study branch to `origin`.
7. Verify the remote branch resolves to the new commit.
8. Record the branch, commit SHA, push result, and remote verification in the next append-only publication entry in `Path.md`.

If commit, authentication, network, remote protection, or push verification fails, the phase status is `Publish blocked`, not `Complete`. Preserve the local commit and failure evidence, report the blocker, and do not begin the next phase until the push succeeds. No force-push, history rewrite, or branch deletion is allowed without explicit user authorization.

## 3. Target repository and engineering layout

The implementation will create the following responsibility-separated structure. Equivalent refinements are allowed only if the trust boundaries remain unchanged and the deviation is logged.

```text
.
|-- README.md
|-- LICENSE
|-- CITATION.cff
|-- WorkPlan.md
|-- Path.md
|-- CLAIMS.md
|-- CLAIM_ELIGIBILITY.md
|-- REPRODUCE.md
|-- pyproject.toml
|-- requirements.lock
|-- configs/
|   |-- study/pead_main_v1.yaml
|   |-- access/{p_only,raw_g,oracle_g}.yaml
|   |-- tracks/{exact,near,reversal,scope,evidence}.yaml
|   |-- domains/*.yaml
|   |-- mechanisms/*.yaml
|   |-- diagnostics/*.yaml
|   |-- methods/*.yaml
|   |-- holdouts/*.yaml
|   |-- requirements/pead_v1_requirements.yaml
|   |-- tracks/near_distance_registry.yaml
|   `-- metrics/*.yaml
|-- src/pead/
|   |-- core/
|   |-- world/
|   |-- labels/
|   |-- projections/
|   |-- tracks/
|   |-- domains/
|   |-- baselines/
|   |-- mavs/
|   |-- metrics/
|   |-- audits/
|   `-- reports/
|-- scripts/
|-- tests/
|   |-- unit/
|   |-- property/
|   |-- metamorphic/
|   |-- integration/
|   |-- blind_contract/
|   `-- stress/
|-- banks/
|   |-- development/
|   |-- calibration/
|   |-- public_validation/
|   `-- sealed/
|-- manifests/
|   |-- custody/
|   |-- allocations/
|   `-- method_cards/
`-- results/
    |-- raw/<run_id>/
    |-- processed/<run_id>/
    |-- audits/<run_id>/
    |-- reports/<run_id>/
    `-- manifests/<run_id>/
```

## 4. Data, truth, and access contracts

The foundational immutable records are:

- `WorldState`: complete latent causal world.
- `PredictiveState`: declared prediction-facing state `p(x)`.
- `GovernanceState`: raw, visible governance evidence that excludes latent truth and MAVS diagnostics.
- `OracleState`: latent governance variables used only for upper-bound and generator sanity checks.
- `AuthorizationLabel`: `Accept`, `Reject`, or `Escalate`, with reason class and rule lineage.
- `CaseRecord`, `PairRecord`, and `SequenceRecord`: content-addressed evaluation units and lineage.
- `ScopeContract`: `(failure family, context, response, allowed influence)`.
- `MethodDecision`: decision, named scores, operating point, trace, resource use, and projection hash.
- `AuditRecord`: gate, severity, evidence pointers, invalidation scope, and status.

Generators have no authority to label cases. Generator modules may emit only latent facts, surface content, causal lineage, registered interventions, and predictive/governance parents. They may not assign, cache, carry, infer, or serialize terminal authorization labels. Labels are produced only by the two independent authorization engines after generation.

The following controls enforce this separation:

- surface templates and authorization logic live in different module trees;
- no surface template has a one-to-one mapping to a terminal label;
- static source scanning rejects generator imports, symbols, or branches that implement `Accept`, `Reject`, or `Escalate` logic;
- label-swapped surface/property tests prove that template identity does not determine authorization;
- every pair carries an intervention proof naming changed authorization parents and byte-verifying unchanged predictive parents;
- generated artifacts have separate unlabeled fact and evaluator-label schemas, and the generator schema has no label field.

The runner must never give a `WorldState` to a method. The only legal route is:

```text
WorldState -> frozen AccessProfile -> sealed projection -> method decision commit
           -> hidden label reveal -> evaluator -> immutable trace -> audits
```

Every method receives one of three access profiles:

- **P-only:** `PredictiveState` only; tests prediction sufficiency.
- **Raw-G:** the same `PredictiveState` plus the same registered raw `GovernanceState`; tests architecture under equal information.
- **Oracle-G:** Raw-G plus latent governance truth; sanity/upper bound only and never a headline baseline.

Oracle-G contains both the deterministic rule evaluator and one high-capacity learned sanity comparator. The learned Oracle-G comparator uses the frozen MLP architecture in Section 6, receives the canonical Oracle-G rendering, and is trained only to detect malformed representations or interfaces. Its result is non-headline; failure blocks the representation-sanity gate but can never redefine or vote on ground truth.

## 5. Training, evaluation, and anti-overfitting doctrine

### 5.1 What is trained

Trainable P-only methods:

- regularized logistic regression;
- gradient-boosted trees;
- MLP;
- canonical-record sequence model;
- reject-option and conformal variants where their calibration contains learned parameters.

Trainable Raw-G methods:

- regularized logistic regression and decision tree;
- gradient-boosted trees;
- MLP;
- sequence encoder;
- provenance/dependency GNN;
- Bayesian network or factor-graph parameterization where applicable;
- learned judge/verifier benchmark adapter;
- learned scalar-risk compression;
- mixture/stacked ensemble.

Non-trained or fixed methods:

- confidence, uncertainty, disagreement, and deterministic self-consistency gates;
- declarative policy engine and validator stack;
- reference authorization evaluators;
- primary frozen MAVS-GC and MAVS-GC + DS-CF;
- fixed MAVS scalarization and fixed component ablations;
- Oracle rule evaluator.

If a fixed MAVS threshold or coefficient is calibrated during development, that process is treated as tuning and is frozen before the blind bank is unlocked. The primary DS-CF condition remains an explicit governance transformation, not a predictor retraining exercise.

#### 5.1.1 Frozen trainable-method specifications

All library versions are exact-pinned in `requirements.lock`; container, accelerator, and model-weight hashes are recorded in the freeze manifest. All neural methods use three training seeds `{101, 211, 307}`. Model selection uses mean protected calibration utility, then worst-seed utility, then lower parameter count, then lower resource cost. Early stopping monitors the registered development objective, never public-validation or holdout metrics. Unless a row states otherwise, the maximum training volume is the complete registered development partition for that access profile, the calibration volume is the complete registered calibration partition, and no resampling may cross pair/sequence/family groups.

| Method | Frozen architecture/implementation | Input rendering and preprocessing | Training data | Optimizer/search and maximum trials | Training schedule and seeds | Calibration/selection | Compute ceiling | Mandatory blind evaluation |
|---|---|---|---|---|---|---|---|---|
| Logistic regression | `sklearn.linear_model.LogisticRegression`, multinomial, `saga`, `max_iter=5000` | Canonical tabular; train-only median imputation, missing indicators, train-only standardization, one-hot categories with unknown bucket | Full applicable development partition; group-atomic | penalty `{l1,l2}` x `C {1e-4,1e-3,1e-2,1e-1,1,10,100}` = 14 trials | Three seeds; convergence failure is retained | Multinomial temperature scaling; lexicographic operating point | 1 CPU-hour/trial, 8 GB RAM | All applicable exact, near, reversal, scope, evidence, structural, and domain banks |
| Decision tree | `sklearn.tree.DecisionTreeClassifier`, cost-complexity pruning | Same canonical tabular pipeline | Full applicable development partition; grouped CV | `max_depth {4,8,16,None}` x `min_samples_leaf {1,10,50}` = 12 trials; pruning alpha chosen inside development by grouped five-fold CV | Three seeds | Isotonic calibration only if every class has >=1,000 calibration opportunities; otherwise Platt | 1 CPU-hour/trial, 8 GB | Same independent battery; report rule depth and unstable splits |
| GBDT | `sklearn.ensemble.HistGradientBoostingClassifier`, three one-vs-rest heads with normalized scores | Native numeric/categorical canonical tabular rendering; missing values preserved | Full applicable development partition; group-atomic | `learning_rate {0.03,0.1}`, `max_iter {200,500}`, `max_leaf_nodes {15,31}`, `l2_regularization {0,1}` = 16 trials | Early stop after 20 development iterations without >=0.001 protected-objective gain; three seeds | Temperature scaling and registered terminal-policy sweep | 4 CPU-hours/trial, 16 GB | Full battery plus label-prior shift and nonlinear leakage challenge |
| MLP | Tabular network `d_in -> 512 -> 256 -> 128 -> 3`; LayerNorm, GELU, dropout 0.10 after each hidden layer | Canonical tabular vector; train-only transformations identical to logistic regression | Full applicable development partition; group-atomic | AdamW; learning rate `{1e-4,3e-4,1e-3}` x weight decay `{1e-5,1e-4}` = 6 trials | Batch 256; maximum 100 epochs; patience 10; gradient norm 1.0; seeds `{101,211,307}` | Temperature scaling; checkpoint tie-break above | 8 GPU-hours/trial on <=24 GB GPU, or declared CPU equivalent | Full battery, three-seed dispersion, nuisance and calibration shift |
| Sequence encoder | Typed-record Transformer: 4 encoder layers, `d_model=256`, 8 heads, FFN 1024, dropout 0.10, learned `[CLS]`, three-class head | Deterministic field-name/value token stream; 32,768-token unigram vocabulary trained on development text only; NFC normalization; numeric bucket tokens; `[UNK]`; maximum 512 tokens; deterministic head+tail truncation manifest | Full applicable development partition; vocabulary also development-only | AdamW; learning rate `{1e-4,3e-4}`, weight decay `{0.01,0.1}`, warmup `{0.05,0.10}` = 8 trials | Batch 128; maximum 60 epochs; patience 8; gradient norm 1.0; three seeds | Temperature scaling; lower truncation rate breaks ties before resource tie-break | 16 GPU-hours/trial on <=24 GB GPU | Unseen templates/grammar, lexical leakage, truncation parity, two-domain transfer |
| Provenance/dependency GNN | 4-layer relational GCN, hidden 256, relation embedding 64, residual LayerNorm/ReLU/dropout 0.10, attention global pooling, 2-layer context MLP, three-class head | Canonical graph; stable node/edge ordering; train-only scalar normalization; unknown node/edge types mapped to registered unknown types; no graph truncation unless declared | Full applicable development graph partition; group-atomic | AdamW; learning rate `{1e-4,3e-4}`, weight decay `{1e-5,1e-4}`, hidden `{128,256}` = 8 trials | Batch 64 graphs; maximum 80 epochs; patience 10; three seeds | Temperature scaling; exact graph-retention audit required | 24 GPU-hours/trial on <=24 GB GPU | Unseen topology/depth/source-sharing, graph canaries, domain transfer |
| Bayesian network/factor graph | `pgmpy` hill-climb structure search with BIC score, maximum indegree 4; Bayesian parameter estimator | Canonical tabular discretized by train-only quantiles; missing is an explicit state | Full applicable development partition; grouped bootstrap | Quantile bins `{8,16}` x BDeu equivalent sample size `{1,5,10}` = 6 trials; deterministic hill-climb order | Three bootstrap/group seeds; maximum 100,000 structure operations | Posterior predictive calibration; choose lowest-edge model on tie | 8 CPU-hours/trial, 32 GB | Held-out policy forms, dependency structures, and ambiguity; representation sanity |
| Reject-option classifier | Frozen MLP above with terminal loss plus coverage penalty; three-class head remains explicit | Same tabular input as MLP | Full applicable development partition; group-atomic | MLP grid x coverage penalty `{0.1,1,10}` = 18 trials maximum | MLP schedule; three seeds | Penalty/threshold selected only on calibration under same protected objective | 8 GPU-hours/trial, 24 GB | Complete error-coverage frontier; forced-certainty and escalate-all stress |
| Static conformal | Base probabilistic logistic/GBDT/MLP selected without conformal results; split conformal score `s(x,y)=1-p_y(x)` | Base-method rendering; group-atomic calibration examples | Frozen base development checkpoint plus complete untouched calibration partition | `alpha {0.01,0.025,0.05,0.10,0.20}`; finite-sample quantile `ceil((n+1)(1-alpha))/n`; no additional search | No retraining beyond base model | Singleton prediction set gives terminal class; non-singleton/empty set gives `Escalate`; operating point selected on calibration | Base-method ceiling plus 1 CPU-hour | Coverage under shift, exact twins, near ladder, structural/domain holdout; guarantees bounded to assumptions |
| Adaptive conformal | Same nonconformity score; prequential window `{256,1024}` with registered delayed-label availability only | Sequence-ordered calibrated probabilities; no hidden/current label access | Frozen base checkpoint, calibration partition, then permitted past labels only | `alpha {0.025,0.05,0.10}` x window `{256,1024}` = 6 settings | Frozen base checkpoint; no gradient updates | Initial calibration split then causal window updates from permitted past labels only | Base ceiling plus 2 CPU-hours | Reversal sequences, drift, delayed labels, and no-label ablation |
| Learned scalar risk | Raw-G encoder matched to MLP capacity through a single scalar bottleneck, then two frozen thresholds | Canonical Raw-G tabular; one scalar is the only terminal input | Full Raw-G development partition; group-atomic | MLP optimizer grid = 6 trials; scalar monotonic penalty `{0,0.1}` = 12 trials | MLP schedule; three seeds | Two thresholds selected lexicographically on calibration | 8 GPU-hours/trial, 24 GB | Central reduction test on composition, scope, reversal, ambiguity, and domain transfer |
| Stacked ensemble | Base predictions from logistic, GBDT, MLP, sequence, and GNN when applicable; multinomial logistic meta-learner | Out-of-fold base scores only; five folds grouped by pair/sequence/latent/template/provenance lineage | Development only; out-of-fold base scores; untouched calibration for final stack | Meta `C {0.01,0.1,1,10}` = 4 trials; no blind/public predictions used for fitting | Three grouped fold assignments derived from registered seeds | Refit base models on full development only after meta selection; calibrate final stack on untouched calibration | Sum of base ceilings + 4 CPU-hours | Full independent battery; compare to best constituent and report stacking failure |
| Judge/verifier | Local `Qwen/Qwen2.5-7B-Instruct`, version `2.5`, exact weight/tokenizer SHA-256 recorded before any training run; no provider substitution | Canonical sequence rendering with frozen system/user templates; output grammar `{"decision","scores","reason"}` | No fine-tuning; development smoke cases for parser only; calibration only for any threshold | No fine-tuning; temperature `0`, top-p `1`, top-k disabled, one sample; maximum 2,048 input and 256 output tokens; one call/case; one retry only for transport failure | Deterministic greedy decoding; retry reuses identical request ID | No prompt edits after development smoke; thresholds, if any, use calibration only | 1 call/case, <=2,304 tokens/case, <=2 GPU-seconds/case target; hard run ceiling declared in method card | All sequence-compatible blind banks; parser failure, prompt leakage, and reproducibility tolerance audit |
| Learned Oracle-G sanity model | Frozen MLP architecture above, with Oracle-G inputs and separate non-headline config | Canonical Oracle-G tabular rendering; same preprocessing rules | Full Oracle-G development partition; non-headline | MLP grid = 6 trials; three seeds | Same MLP schedule | Temperature scaling; cannot participate in H1/H2 ranking | 8 GPU-hours/trial, 24 GB | Structural/domain sanity subset; failure blocks representation validity, never changes labels |

The judge/verifier prompt contract is immutable and contains: role, permitted evidence fields, exact three-action definitions, prohibition on inferring hidden fields, required JSON schema, and no demonstrations from calibration or holdout cases. Requests are content-addressed and cached by model hash + prompt hash + projection hash. Parser rejection yields a recorded method failure; retries do not alter content. Exact greedy equality is expected on the pinned environment; otherwise the pre-freeze tolerance rule requires identical parsed decision and scores within `1e-6`.

#### 5.1.2 Training volumes and selection budgets

Open-bank volumes are separate from the claim-bearing canonical bank:

| Partition | Domains | Exact pairs/domain | Near pairs/domain | Reversal sequences/domain | Scope cases/domain | Evidence cases/domain | Use |
|---|---:|---:|---:|---:|---:|---:|---|
| Development | D1-D6 | 4,000 | 2,000 | 1,000 | 2,800 | 1,500 | Model fitting and grouped CV |
| Calibration | D1-D6 | 1,000 | 500 | 250 | 700 | 375 | Calibration and operating point only |
| Public validation | D1-D6 | 1,000 | 500 | 250 | 700 | 375 | Sanity/power/report rehearsal only |

Each trainable method receives all applicable registered development cases, no more than its tabled trial count, exactly three training seeds where relevant, and exactly one final calibration pass per retained checkpoint. A failure to train within the ceiling is reported as method failure; data, trials, epochs, architecture, or ceiling may not be expanded in response to comparative performance.

#### 5.1.3 Baseline method cards and fidelity

Every baseline has a release-blocking method card under `manifests/method_cards/<method_id>.yaml` with: source/reference, exact implementation identity and hashes, fidelity class (`faithful reproduction`, `mechanism-level adaptation`, `simplified benchmark implementation`, `proxy comparator`, or `official external implementation`), reproduced elements, adapted elements, required information, deviations, limitations, training and inference budgets, and eligible claims. Reports must not describe an adaptation or proxy as an official implementation.

MAVS human engineering effort, diagnostic design, scope-contract authorship, and rule construction are reported separately from training compute. Equal information and compute do not imply equal human design cost.

### 5.2 Training benchmark versus claim-bearing benchmarks

The claim-bearing tests must be **structurally different from the training benchmark**, not merely different rows or random seeds.

| Partition | Permitted content | Scientific role | Isolation requirement |
|---|---|---|---|
| Development/training | Open mechanisms, open policy forms, open graph families, domains D1-D6, development templates and seeds | Train models, debug code, fit representations | May be regenerated; never claim-bearing |
| Calibration | Disjoint worlds from known mechanisms and templates; no holdout logical forms | Select thresholds and operating points | No architecture changes after final calibration |
| Public validation | New seeds, nuisance families, and mechanism compositions from known development families | Sanity, power, public figures | Cannot determine final claim |
| Structural holdout | Unseen mechanism families/compositions, policy logical forms, provenance topologies/depths, diagnostic interactions, and intervention types | Causal generalization | Authored and sealed before model tuning ends |
| Domain holdout | Two complete surface domains, provisionally D7 clinical-triage proxy and D8 content/policy-safety proxy | Cross-domain latent-grammar transfer | No templates, feature statistics, examples, labels, or adapter outputs exposed during training |
| Final blind bank | Cross-product of structural holdouts and the two unseen domains, with hidden seeds and held-out nuisance families | Claim-bearing evaluation | Unlocked only after signed freeze; single scientific run |

The complete holdout registry and generation package is signed and sealed in Phase 9A before any Phase 10 training, calibration, or public-validation result exists. If D7/D8 prove invalid during independent domain review, replacement domains must be selected before Phase 9A and the change logged; they cannot be swapped based on method performance.

### 5.3 Brutal independent evaluation

Every trained model must be evaluated on all applicable test families below, none of which may contribute training examples, early-stopping feedback, feature-selection feedback, threshold selection, or hyperparameter selection:

1. **Unseen causal mechanisms:** at least two withheld families or novel three-fact compositions.
2. **Unseen policy grammar:** new logical forms, nesting, temporal clauses, and contradiction patterns rather than changed numeric thresholds.
3. **Unseen provenance graphs:** unseen topology classes, depth ranges, dependency sharing, and compromised-source patterns.
4. **Unseen interventions:** delayed compromise discovery, permission expiry/restore, policy version reversal, rollback loss, and evidence restoration.
5. **Unseen domains:** two complete surface adapters absent from training and calibration.
6. **Unseen scope compositions:** pairwise and higher-order diagnostic interactions withheld from development.
7. **Near-equivalence ladder:** frozen epsilon grid with both divergent and same-label controls.
8. **Reversal sequences:** stale-authorization, detection-latency, and recovery tests.
9. **Evidence sufficiency:** resolvable, reducibly ambiguous, and irreducibly ambiguous banks.
10. **Adversarial nuisance tests:** label-swapped templates, identifier/style/order changes, prior shift, label permutation, canaries, and held-out nuisance generators.
11. **Coverage-collapse tests:** full risk-coverage frontiers and forced operating points that expose reject-all/escalate-all behavior.
12. **Worst-world tests:** catastrophic acceptance, worst mechanism/domain, and worst-decile loss.
13. **Metamorphic tests:** irrelevant interventions preserve labels; causal interventions flip them; scope-inappropriate diagnostics cannot acquire forbidden authority.
14. **Reproduction tests:** clean checkout, fresh environment, regenerated deterministic banks, rerun traces, and conclusion-preserving model tolerances.

### 5.4 Anti-overfitting and contamination controls

- Holdout mechanisms, logical forms, graph families, domain templates, interactions, interventions, nuisance generators, exact seed lists, generation code, distances, ambiguity rules, and allocations are signed and sealed in Phase 9A before the first Phase 10 training run.
- Final case IDs contain no label, domain, mechanism, split, or policy-name information.
- Final text templates never appear verbatim in development or calibration.
- High-capacity leakage adversaries predict authorization, intervention, domain, mechanism, and split from P-only fields. Frozen permutation-derived chance bands govern release.
- Exact and approximate duplicate audits cover lexical, tabular, vector, structural, and graph similarity.
- No final-bank label prevalence is available for threshold setting.
- Early stopping uses development data only. Operating points use calibration data only.
- Hyperparameter spaces, trial counts, compute ceilings, and tie-breakers are pre-registered.
- The same training/calibration case IDs are used within each access profile.
- Raw-G methods receive semantically equivalent canonical tabular, sequence, and graph renderings from the same raw object; every lossy transformation is declared.
- All final-bank access is logged. Manual inspection quarantines affected cases unless pre-authorized for infrastructure audit.
- Scientific underperformance never permits retuning. Infrastructure repair requires invalidation, a documented diff, and complete affected-suite rerun.
- Sensitivity panels and Pareto neighborhoods prevent a conclusion from depending on one favorable threshold.
- Per-domain, per-mechanism, and tail results are reported before macro averages.

### 5.5 Complete registered mechanism inventory

Every mechanism in the specification is implemented, configured, unit-tested, instantiated across valid domains, and represented in the audit/report strata. Simple cases are theorem sanity checks and may not dominate claim-bearing banks.

| ID | Mechanism | Required implementation behavior |
|---|---|---|
| M01 | Authority mismatch | Hold prediction fixed while permission/delegation changes; produce valid `Accept <-> Reject` twins and revoke/restore sequences |
| M02 | Policy conflict | Compose active policy constraints independently of predictive support; test new logical forms and policy versions |
| M03 | Provenance dependence | Distinguish independent sources from shared/compromised sources using graph structure, not only counts |
| M04 | Evidence masking | Mask benign or harmful witnesses; route unresolved visible states to evidence-derived `Escalate` |
| M05 | Reversibility shift | Hold the candidate fixed while rollback availability or irreversibility changes authorization |
| M06 | Consequence escalation | Vary registered impact class/budget without leaking it into P-only fields |
| M07 | Temporal validity | Expire/restore permission, policy, exception, or evidence with stale-authorization and recovery tests |
| M08 | Shared premise corruption | Model correlated specialist support caused by one wrong latent premise and preserve DS-CF scope semantics |
| M09 | Counterfactual fragility | Evaluate registered alternate views and prevent unregistered view access |
| M10 | Constraint interaction | Require multi-fact composition, including at least one claim-bearing three-or-more-fact rule |
| M11 | Scope boundary | Present surface patterns outside a diagnostic's authorized context; ground truth must remain unchanged |
| M12 | Ambiguity class | Prove multiple terminal labels remain compatible with visible evidence and no permitted resolution action remains |

### 5.6 Complete MAVS ablation inventory

All ablations use the same Raw-G projection unless the ablation explicitly tests removal of governance information. Every ablation logs its changed component and preserves all unrelated code/configuration.

| ID | Condition | Registered causal question |
|---|---|---|
| A00 | Prediction-only MAVS | Are gains caused by governance information? |
| A01 | No provenance diagnostics | Does source/dependency evidence causally matter? |
| A02 | No policy diagnostics | Can authorization work without policy conflict/validity? |
| A03 | No authority diagnostics | Does permission/delegation remain necessary? |
| A04 | No evidence-availability diagnostics | Does hidden missingness force terminal errors? |
| A05 | No counterfactual fragility | Which alternate-view failures are missed? |
| A06 | No contextual weights | Does context-dependent specialist influence matter? |
| A07 | No mitigation | Does safe-consistency recall protection prevent FRR/escalation? |
| A08 | No hard veto | Are certified harmful cases accepted by threshold logic? |
| A09 | No escalation | What binary error is created by ambiguity? |
| A10 | No scope contracts | Does unbounded diagnostic authority cause scope leakage? |
| A11 | One fixed scalar | Can hand-designed scalar aggregation replace structure? |
| A12 | One learned scalar | Can high-capacity scalarization replace structure under equal information? |
| A13 | Flat Raw-G classifier | Does generic terminal function approximation suffice? |
| A14 | Original MAVS-GC | Does DS-CF repair the registered correlated-scope failure? |
| A15 | Full MAVS-GC + DS-CF | Reference fixed structured-governance condition |

### 5.7 Outcome tiers and claim boundaries

| Outcome | Objective condition | Maximum permitted interpretation |
|---|---|---|
| Integrity-valid negative | All integrity gates pass; H1 fails | Registered PEAD formulation did not establish prediction insufficiency |
| Paradigm support | Exact/near P-only frontier matches the registered lower bound and Raw-G escapes on blind families | Prediction-facing state is insufficient on the registered PEAD class |
| Generalized paradigm support | Paradigm effect persists across structural and domain holdouts | Effect covers the broad registered class, not one grammar |
| Architectural support | MAVS improves a pre-registered protected/scope/transfer frontier over the best equal-information flat Raw-G method | Structured MAVS governance adds value in the registered conditions |
| Strongest result | Generalized H1, architectural support, scalar-compression failure, and audit-perfect reproduction | Paradigm-level impact potential; not universal validity, deployment readiness, or zero risk |

Forbidden conclusions include universal prediction insufficiency, universal MAVS optimality, deployment certification, zero-risk claims, treating escalation as safety, or claiming official external benchmark execution when only an adaptation/projection was used.

### 5.8 Risk controls and mandatory stop conditions

| Risk ID | Risk | Preventive implementation | Stop or claim action |
|---|---|---|---|
| R1 | Trivial permission-bit benchmark | Composition, graph, time, scope, ambiguity, anti-triviality review | Fail the affected domain/release bank |
| R2 | Predictive leakage | Firewall, nuisance balance, canaries, multi-family adversaries | Quarantine and regenerate the bank |
| R3 | MAVS-coupled truth | Independent generators/evaluators and dependency audit | Invalidate the study version |
| R4 | Weak Raw-G baselines | GBDT, neural, graph, rule, validator, judge, scalar, ensemble | Prohibit architecture claim |
| R5 | Escalation/rejection collapse | Joint UAR/FRR/escalation/coverage and Pareto frontiers | Prohibit safety-success claim |
| R6 | No transfer | Structural plus two-domain holdouts | Limit claim to seen families |
| R7 | Label ambiguity bug | Dual engines and compatible-world proof | Block release |
| R8 | Post-freeze tuning | Signed freeze and access logs | Invalidate blind result |
| R9 | Compute inequity | Budget classes, matched IDs/trials, resource audit | Downgrade/prohibit fairness claim |
| R10 | Overloaded scope | Prioritize integrity and causal diversity; stage optional high-cost methods transparently | Cut non-primary extras before core gates |
| R11 | MAVS loses equal-information test | Retain and analyze the result | No MAVS architecture claim |
| R12 | Reproduction mismatch | Locks, manifests, tolerance policy, clean rebuild | Block reproducibility and affected release claims |

Execution stops immediately for any non-identical released exact twin, any released dual-label disagreement, forbidden method access, final-bank contamination, post-freeze tuning, missing headline trace lineage, claim-changing clean-reproduction failure, or evidence that truth generation depends on MAVS code.

### 5.9 Canonical claim-bearing allocation manifest

`manifests/allocations/final_claim_bank_v1.json` is designed and hash-committed in Phase 9A before Phase 10 training. The following allocations are normative, not targets that may be rebalanced after results:

| Track | Exact claim-bearing allocation |
|---|---|
| Exact | `8 domains x 2,000 = 16,000 pairs / 32,000 worlds` |
| Near | `8 domains x 1,000 = 8,000 pairs / 16,000 worlds`; exactly 125 pairs/domain at each epsilon in `{0,1e-6,1e-5,1e-4,1e-3,1e-2,5e-2,1e-1}` |
| Reversal | `8 domains x 500 = 4,000 sequences`; step lengths are exactly 20% four-step, 60% six-step, 20% eight-step, giving exactly 24,000 steps |
| Scope | `8 domains x 7 DS-CF diagnostics x 4 canonical banks x 100 = 22,400 cases`; canonical banks are positive, matched negative, boundary, and adversarial out-of-scope |
| Evidence sufficiency | `8 domains x 3 classes x 500 = 12,000 cases` |
| Matched controls | At least 20% of paired/sequence volume, additional to the canonical totals where necessary; includes composition, nuisance, prior-shift, and label-permutation controls |

#### 5.9.1 Exact Track I sub-banks

For each domain's 2,000 exact pairs:

| Sub-bank | Pair type | Pairs/domain | Required balance and certificate |
|---|---|---:|---|
| I-A | `Accept <-> Reject` | 800 | Exactly 400 in each pair orientation; byte-identical `PredictiveState`; dual labels |
| I-B | `Accept <-> Escalate` | 400 | Exactly 200 in each orientation; ambiguity certificate for every Escalate member |
| I-C | `Reject <-> Escalate` | 400 | Exactly 200 in each orientation; danger witness plus ambiguity certificate |
| I-N | Same-label exact controls | 400 | 133 Accept/Accept, 133 Reject/Reject, 134 Escalate/Escalate; irrelevant-intervention proof |

Per domain, primary-mechanism quotas are fixed by a largest-remainder rule: M01-M08 receive 167 pairs each and M09-M12 receive 166 each, totaling 2,000. Within every eligible sub-bank, intervention direction is balanced to within one pair. Exactly 30% of pairs are simple theorem sanity cases and 70% are compositional; at least 40% of all exact pairs use authorization rules with three or more interacting governance facts. Allocation exceptions caused by a mechanism/sub-bank incompatibility must be resolved by the precommitted substitution table, never after outcome inspection.

Global opportunity-label counts are balanced as closely as integer arithmetic permits, with maximum class-count difference of two worlds. Every metric records exact denominators by sub-bank, domain, mechanism, label, intervention, complexity, and consequence class.

The lower-bound implementation separately evaluates:

- deterministic terminal P-only rules;
- randomized terminal P-only rules using registered randomness and expected pair error;
- policies that escalate both twins;
- complete pair-level terminal-error versus coverage frontiers;
- protected UAR/FRR/escalation/coverage at matched operating points;
- pair-level performance, never ordinary row accuracy as the theorem-bearing statistic.

#### 5.9.2 Atomic grouping and opportunity balance

Members of the same pair, sequence, latent-world family, surface-template family, intervention lineage, or provenance-graph lineage receive one `atomic_group_id` and must remain in one partition. Grouped split construction and an overlap audit fail on any cross-partition related unit.

The allocation audit blocks release unless:

- theorem-bearing divergent sub-banks are orientation- and label-balanced;
- every domain and mechanism meets its exact registered quota;
- simple/compositional/three-factor proportions match the manifest;
- ecological imbalance occurs only in a separately named stress bank and never changes headline denominators;
- every protected metric includes numerator and denominator;
- prior-shift and label-permuted banks exist;
- a class-prior-only baseline remains at its registered chance behavior;
- no case or related unit crosses development, calibration, public validation, structural holdout, domain holdout, or blind boundaries.

### 5.10 Typed near-equivalence distance registry

`src/pead/tracks/distances.py` and `configs/tracks/near_distance_registry.yaml` define versioned, field-specific distances before near-bank generation:

| Predictive field type | Frozen distance |
|---|---|
| Scalar | Absolute difference divided by a development-only robust range fixed without authorization outcomes |
| Calibrated probability | Absolute logit difference with clipping at `[1e-6,1-1e-6]`, normalized by a development-only scale |
| Vector | Root-mean-square normalized component distance; dimensions and weights frozen |
| Categorical | `0` for equality, registered mismatch cost otherwise; no outcome-derived cost |
| Set | Weighted Jaccard distance over canonical stable IDs |
| Graph | Weighted normalized graph-edit distance over registered node/edge types; deterministic embedding distance may be reported only as a secondary sensitivity |
| Text-derived predictive representation | Cosine distance between frozen encoder representations plus token-level normalized edit distance, both reported; aggregate uses precommitted maximum |
| Missing value | Typed missingness mismatch cost fixed per field; missing/missing is zero |

The aggregate is a precommitted weighted maximum of normalized field distances so one large change cannot be hidden by averaging. Field ranges and weights are calibrated on unlabeled development predictive states only. No authorization label, method output, or public-validation outcome may influence distance calibration. Each domain contributes exactly 125 pairs at each epsilon; at each epsilon, 25 pairs are I-A-like, 25 I-B-like, 25 I-C-like, and 50 same-label controls.

### 5.11 Early Diagnostic Sciences registry

Before Phase 4 begins, Phase 0 freezes schema/configuration and Phase 1 implements `src/pead/core/diagnostic_registry.py`. Each file under `configs/diagnostics/` contains:

- stable diagnostic ID, semantic name, version, and retirement/supersession rule;
- failure family and applicable domain/context predicates;
- positive, matched-negative, boundary, and adversarial out-of-scope generators;
- prescribed response and permitted influence path;
- prohibited influence paths and maximum authority;
- expected pairwise/set interaction partners;
- signal and decision monotonicity contracts;
- nuisance-invariance requirements;
- required scope metrics and minimum sample allocations.

DS-CF registers seven separate diagnostics before scope-bank generation:

| Stable ID | Signal | Meaning | Authority constraint |
|---|---|---|---|
| `DSCF-ZC-v1` | `z_c` | Correlation presence | Investigation/weak severity only; never veto alone |
| `DSCF-ZH-v1` | `z_h` | Harmful correlation | Primary harmfulness signal subject to witness conjunction |
| `DSCF-ZS-v1` | `z_s` | Safe consistency | Bounded mitigation; cannot override certified veto |
| `DSCF-ZM-v1` | `z_m` | Missing independent evidence | Danger/ambiguity witness; missingness alone cannot certify harm |
| `DSCF-ZP-v1` | `z_p` | Policy conflict | Explicit constraint witness within registered policy scope |
| `DSCF-ZO-v1` | `z_o` | Overconfident consensus | Soft danger evidence; not independently terminal |
| `DSCF-ZF-v1` | `z_f` | Counterfactual fragility | Alternate-view witness using only permitted views |

Phase 8 implements the signals and governed composition against this frozen registry; it may not retroactively change Phase 4 scope-bank definitions.

### 5.12 Complete ambiguity certification

Sampling compatible worlds is allowed only for non-claim-bearing stress discovery. Every claim-bearing resolvable, reducibly ambiguous, irreducibly ambiguous, I-B, I-C, or Escalate case requires a complete certificate produced by exact finite enumeration, SAT/SMT solving, model checking, exhaustive symbolic constraint evaluation, or a conservative proof system whose completeness conditions are satisfied for that grammar.

Every `AmbiguityCertificate` contains:

- visible-state and projection hashes;
- compatible terminal authorization classes;
- at least one witness world per compatible class;
- permitted, available, unavailable, and exhausted resolution channels;
- proof method, solver/version/configuration, proof hash, and proof-completeness status;
- unique-authorization proof where a case is declared resolvable;
- reason that no permitted resolution channel remains where irreducible ambiguity is declared.

Timeout, `unknown`, incomplete search, or a failed proof may conservatively produce an explicitly typed non-claim-bearing unresolved case, but may not certify unique authorization, irreducible ambiguity, or absence of resolution. Certificate verification is independent of the generator and both label engines.

### 5.13 Operational blind-bank custody and chronology

All scientifically substantive holdout design occurs in Phase 9A, before Phase 10 training, calibration, or public-validation inspection. This includes mechanism families/compositions, policy logical forms, graph topology families, scope interactions, intervention classes, nuisance generators, domain templates, exact seed ranges/lists, generation code, allocation rules, distance rules, and ambiguity-proof rules. Their hashes are signed before Phase 10 begins.

Seed namespaces are disjoint and immutable:

- development: `1,000,000-1,999,999`;
- calibration: `2,000,000-2,499,999`;
- public validation: `3,000,000-3,499,999`;
- structural holdout: `7,000,000-7,999,999`;
- domain holdout: `8,000,000-8,999,999`;
- final blind cross-product: `9,000,000-9,999,999`.

Exact selected blind seed lists are encrypted and hash-committed in Phase 9A; merely knowing the namespace is insufficient to materialize the bank.

The custody protocol is concrete:

1. A clean custody workspace under a dedicated `pead-blind-evaluator` OS identity runs the precommitted holdout generator. The development workspace and method processes do not mount or read that workspace.
2. Case facts, allocation assignments, and labels are packaged separately with AES-256-GCM. Only content hashes, counts, allocation metadata, generator/config hashes, and ciphertext are visible before method freeze.
3. The encryption key is generated and held in the OS credential store accessible only to the custody identity. It is absent from the repository, shell history, environment lock, method workspace, and Codex development context.
4. For a solo project, custody review may be performed by a separately prompted evaluator session that did not implement the component, but the key remains controlled by the sealed local process. Reports disclose this as internal separation, not external validation.
5. Phase 11 supplies the signed method-freeze manifest to the custody process. The process unlocks only if every precommitted holdout hash and every method/checkpoint/operating-point/report hash verifies.
6. Materialization is one-shot, content-addressed, read-only, and append-logged. Repeated materialization must reproduce the same case hashes or fail.
7. The evaluation process streams one case at a time. Method subprocesses receive only the registered sealed projection, never case facts, seed, domain/mechanism identity, custody metadata, or labels.
8. Hidden labels remain separately encrypted until the method decision and trace hash are committed. Only the evaluator can reveal and score that label.
9. Every custody, unlock, materialization, projection, label-reveal, and manual access attempt is timestamped in an append-only signed log.
10. Any pre-freeze access, hash mismatch, missing log event, key exposure, non-one-shot mutation, or direct method access invalidates the blind bank and requires a new study version with new hidden seed lists and key.

Phase 11 may verify, freeze, unlock, materialize, and audit contamination. It may not design or change any mechanism, grammar, topology, interaction, intervention, nuisance generator, domain template, seed allocation, distance, ambiguity rule, or quota.

### 5.14 Human audit program

Signed artifacts are written under `results/audits/<run_id>/human/`. Each records reviewer identity or pseudonymous role, independence relationship, reviewed component/sample IDs, checklist version, findings, corrections, unresolved concerns, signature/hash, and pass/fail status.

Required checkpoints are:

- separate review of each label engine and their independence;
- access-projection and Raw-G semantic-parity review;
- stratified samples from every domain x mechanism x authorization-label class;
- every headline failure and every quarantined case;
- benchmark non-triviality and absence of direct label flags;
- every baseline method card and fidelity classification;
- verification that every negative scientific result appears in reports.

For solo execution, a separately prompted evaluator session that did not implement the reviewed component may satisfy internal separation when its prompt/context identity is retained. It must be disclosed as internal independent review, never external human validation.

### 5.15 Strict failure-card schema

`FailureCard` is a versioned strict schema containing:

- immutable case, pair, or sequence ID;
- run, commit, environment, config, method, projection, and trace hashes;
- domain, mechanism, split, and atomic-group identity;
- expected and observed action, visible evidence hash, and protected-error type;
- diagnostic state, access profile, and applicable scope contract;
- root-cause classification and evidence;
- case-validity verdict;
- containment, quarantine, repair, and invalidation status;
- affected claims and outcome tiers;
- exact reproduction command and referenced artifacts.

The failure-card audit enforces a bijection: every qualifying protected error, scope anomaly, label disagreement, access violation, quarantine, invalidation, and reproduction mismatch has exactly one canonical card, and no card points to a nonexistent qualifying event. Missing, duplicate, or schema-invalid cards block release and selective-reporting claims.

## 6. Phase plan

### Phase 0 - Research charter, claim ledger, and execution controls

**Scope**

Freeze hypotheses H1/H2, claims C1-C6, nulls, non-claims, access profiles, outcome tiers, stop conditions, study versioning, paper boundary, negative-result policy, and the causal-rejection closure map. Establish `WorkPlan.md`/`Path.md` discipline and record the empty-repository/result baseline.

**Files**

- `WorkPlan.md`, `Path.md`, `CLAIMS.md`
- `configs/study/pead_main_v1.yaml`
- `configs/holdouts/holdout_registry_v1.yaml`
- `configs/diagnostics/{schema,ds_cf_zc,ds_cf_zh,ds_cf_zs,ds_cf_zm,ds_cf_zp,ds_cf_zo,ds_cf_zf}.yaml`
- `configs/requirements/pead_v1_requirements.yaml`
- `configs/metrics/protected_objective_v1.yaml`
- `docs/blind_custody_protocol.md`
- `README.md`, `CITATION.cff`, `pyproject.toml`

**Code and implementation method**

- Add typed configuration schemas and a schema-validation command.
- Encode every claim's required metrics, splits, audits, and forbidden wording.
- Encode the lexicographic operating-point objective: unsafe-acceptance constraint, then FRR, unnecessary escalation, resource cost, and frozen low-complexity tie-break.
- Add source-document hashes and base commit to the study manifest.
- Freeze the diagnostic-registry schema, stable DS-CF diagnostic identities, strict failure-card schema, requirement-ID schema, and blind-custody protocol before dependent implementation.

**Verification and completion gates**

- Every specification concern maps to at least one implementation control, executable audit, gate, and retained artifact.
- Schema validation passes.
- H1 and H2 are independently reportable.
- Negative scientific outcomes are explicitly publishable.
- Every normative specification clause has a stable requirement ID and planned files/tests/artifacts/failure/claim mapping.
- Phase 0 evidence is recorded in `Path.md`.

### Phase 1 - Core immutable infrastructure and safe result hygiene

**Scope**

Implement typed records, canonical serialization, IDs, hashing, seed lineage, configuration loading, registries, immutable run layout, trace writing, and safe cleanup.

**Files**

- `src/pead/core/{types,ids,hashing,seeds,config,registry,runner,traces,paths}.py`
- `src/pead/core/{diagnostic_registry,requirement_registry}.py`
- `scripts/clear_results.py`, `scripts/validate_config.py`
- `tests/unit/test_{types,ids,hashing,seeds,config,paths,traces}.py`
- `tests/property/test_canonicalization.py`

**Code and implementation method**

- Use frozen dataclasses/Pydantic-compatible schemas with explicit schema versions.
- Canonicalize UTF-8 objects with sorted keys, frozen float quantization, sorted graph/set fields, and normalized candidate actions.
- Hash individual fields and complete records.
- Write append-only JSONL and Parquet-compatible traces with atomic finalization.
- Generate content-derived world, pair, sequence, run, and artifact IDs.
- Implement deletion guards using resolved absolute paths and manifest membership.
- Implement typed diagnostic and requirement registries that reject missing scope/authority/version/traceability fields.

**Verification and completion gates**

- Duplicate deterministic runs produce byte-identical canonical records and IDs.
- Serialization order changes do not change canonical hashes.
- ID collision/property stress tests pass.
- Malformed or incomplete traces are rejected.
- Diagnostic and requirement registries reject unversioned, duplicate, or incomplete entries.
- Cleanup dry-run and adversarial path tests prove repository-root and out-of-results deletion impossible.

### Phase 2 - Independent authorization truth system

**Scope**

Implement the declarative policy DSL, parser, total deterministic evaluator, a separately coded procedural reference evaluator, compatible-world ambiguity logic, rule fixtures, and label agreement auditing.

**Files**

- `src/pead/labels/{dsl,parser,evaluator_dsl,evaluator_reference,ambiguity,reasons}.py`
- `configs/mechanisms/*.yaml`, `configs/policies/*.yaml`
- `scripts/audit_labels.py`
- `tests/unit/test_policy_dsl.py`
- `tests/property/test_label_*.py`
- `tests/metamorphic/test_authorization_invariants.py`

**Code and implementation method**

- DSL supports typed predicates, logical composition, temporal validity, graph conditions, consequence thresholds, evidence availability, and explicit ambiguity rules.
- Reference evaluator must not parse or import the DSL evaluator and receives only serialized latent facts.
- Both evaluators return label, reason class, satisfied/violated constraints, ambiguity basis, and rule lineage.
- Certify claim-bearing ambiguity only by exact finite enumeration, SAT/SMT, model checking, exhaustive symbolic evaluation, or a completeness-justified conservative proof procedure. Sampling is stress-only and cannot certify uniqueness or irreducibility.
- Emit and independently verify the complete `AmbiguityCertificate` schema in Section 5.12.

**Verification and completion gates**

- `100%` dual-engine agreement on every released fixture/case.
- Oracle rule evaluator obtains `100%` on valid deterministic fixtures.
- Positive, negative, boundary, contradictory, and temporal fixtures exist for every rule family.
- Every claim-bearing resolvable or ambiguous case has a complete, independently verified certificate; timeout/unknown is never accepted as proof.
- Permission revocation/prohibition monotonicity and irrelevant-intervention invariance pass.
- Any disagreement quarantines the case and blocks dependent release.

### Phase 3 - Causal world registry, exact twins, and near twins

**Scope**

Implement the latent factorization, mechanism registry M01-M12, primary and reference generation paths, exact-twin construction, near-twin perturbations, nuisance controls, and leakage audits.

**Files**

- `src/pead/world/{schema,generator_primary,generator_reference,mechanisms,interventions,nuisance}.py`
- `src/pead/tracks/{exact,near,distances}.py`
- `configs/tracks/near_distance_registry.yaml`
- `configs/allocations/exact_track_i_v1.yaml`
- `src/pead/audits/{equivalence,authorization,leakage}.py`
- `scripts/generate_bank.py`, `scripts/audit_equivalence.py`, `scripts/audit_leakage.py`
- `tests/property/test_twin_invariance.py`
- `tests/metamorphic/test_nuisance_invariance.py`

**Code and implementation method**

- Sample complete unlabeled worlds before any method-specific transformation; generators cannot emit or carry authorization labels.
- Change exactly registered authorization parents outside `PredictiveState` while freezing predictive parents.
- Accept exact pairs only after field-level and byte-level equivalence, dual-label agreement, authorization divergence, and leakage checks.
- Implement I-A Accept/Reject, I-B Accept/Escalate, I-C Reject/Escalate, and I-N same-label exact banks with the exact quotas, orientations, mechanism allocations, complexity proportions, and denominators in Section 5.9.
- Implement the typed distance registry and frozen epsilon allocations in Section 5.10.
- Generate balanced nuisance, label-swapped, irrelevant-intervention, and same-label controls.
- Assign `atomic_group_id` across pair, sequence, latent family, template family, intervention lineage, and provenance lineage; grouped splits are indivisible.
- Implement deterministic/randomized/escalate-both lower-bound evaluators and pair-level error-coverage frontiers.
- Static-scan generator source for prohibited label logic and verify separate unlabeled-fact/label schemas.
- Keep the reference path free of shared authorization functions.

**Verification and completion gates**

- Every divergent exact sub-bank has `PEI == 1` and `ADI == 1`; I-N has `PEI == 1` and same-label invariance.
- Exact sub-bank/domain/mechanism/intervention/complexity quotas match the signed allocation manifest exactly.
- Group-split audit finds zero related units across partitions.
- Generator dependency/source scan, label-swapped surfaces, and intervention proofs pass.
- Same-label controls preserve labels.
- Near pairs respect frozen distance metrics and do not reveal governance interventions.
- Linear, GBDT, sequence, graph, and nearest-neighbor leakage adversaries remain within frozen chance bands or the affected bank is repaired and regenerated.

### Phase 4 - Reversals, scope banks, and evidence-sufficiency boundaries

**Scope**

Implement governance-reversal sequences, Diagnostic Sciences scope contracts, positive/negative/boundary/out-of-scope/composition/nuisance banks, and the three evidence-sufficiency classes.

**Files**

- `src/pead/tracks/{reversal,scope,evidence_sufficiency}.py`
- `src/pead/core/scope_contract.py`
- `src/pead/core/diagnostic_registry.py`
- `configs/diagnostics/*.yaml`
- `configs/tracks/{reversal,scope,evidence}.yaml`
- `tests/property/test_scope_safe_diagnostics.py`
- `tests/metamorphic/test_reversal_fidelity.py`
- `tests/unit/test_ambiguity_proof.py`

**Code and implementation method**

- Encode permission, policy, provenance, rollback, expiry, and evidence-restoration reversals with known change times.
- Generate scope-positive, matched-negative, boundary, adversarial out-of-scope, composition, and nuisance cases for every diagnostic in the already-frozen registry; Phase 4 cannot invent diagnostic semantics.
- Compute ambiguity from compatible worlds and permitted resolution channels.
- Preserve the Paper 1/Paper 2 boundary: fixed methods represent unresolved evidence; adaptive acquisition is out of scope.

**Verification and completion gates**

- Reversal times and recovery states reproduce deterministically.
- Reversal fixtures expose exact change points, restoration points, stale-authorization opportunities, and false-reversal controls needed by the complete Phase 9 metric set.
- Out-of-scope fixtures do not alter truth and cannot acquire unregistered terminal influence.
- Ambiguity proofs reproduce every `Escalate` label.
- Removing all permitted resolution channels converts reducible ambiguity to irreducible ambiguity, not arbitrary rejection.

### Phase 5 - Eight domain adapters and independent validity review

**Scope**

Implement tool execution, cyber response, multi-agent operations, retrieval/provenance, software deployment, financial approval proxy, clinical triage proxy, and content/policy safety adapters.

**Files**

- `src/pead/domains/{base,tool,cyber,multi_agent,retrieval,software,finance,clinical,content}.py`
- `configs/domains/*.yaml`
- `tests/integration/test_domain_contracts.py`
- `results/audits/<review_id>/domain_validity/*.json`

**Code and implementation method**

- All adapters implement the same task, candidate, mechanism, projection, and validation protocol.
- Each domain instantiates at least six mechanism families, including composition and ambiguity.
- At least two domains use graph-dependent authorization; two use temporal reversal; two use policy-grammar composition.
- Authorization may not be exposed as one obvious Raw-G Boolean.
- Apply domain-specific label-swapping and surface anti-shortcut transformations.

**Verification and completion gates**

- Cross-domain schema parity passes.
- Every domain meets anti-triviality minima.
- An evaluator who did not author an adapter reviews substantive meaning, projection defensibility, shortcuts, and bounded proxy claims.
- Two valid domains and their complete templates are selected before Phase 9A and sealed there before the first Phase 10 training run.
- Domain templates, anti-shortcut transforms, and allocation eligibility for all eight domains are complete before Phase 9A holdout sealing; they cannot be redesigned after model results.

### Phase 6 - Projection layer, feature firewall, and equal-information renderings

**Scope**

Implement P-only, Raw-G, and Oracle-G projections; sealed inputs; static/runtime access enforcement; hidden canaries; and canonical tabular, sequence, and graph renderings.

**Files**

- `src/pead/projections/{predictive,raw_governance,oracle,firewall,tabular,sequence,graph}.py`
- `configs/access/{p_only,raw_g,oracle_g}.yaml`
- `src/pead/audits/access.py`
- `scripts/audit_access.py`, `scripts/audit_representation_parity.py`
- `tests/integration/test_access_profiles.py`
- `tests/blind_contract/test_hidden_truth_isolation.py`

**Code and implementation method**

- The projection package is the only package allowed to transform `WorldState` into method input.
- Return immutable objects with no back-reference to hidden state.
- Log field masks, transformations, truncation, missing-value behavior, and projection hashes for every decision.
- Static dependency scanning forbids method imports from hidden world, label, evaluator, and audit modules.
- Runtime proxy logging records forbidden access attempts and inserts randomized hidden canaries.
- A field-by-method matrix proves semantic Raw-G parity across representations.

**Verification and completion gates**

- No forbidden import, attribute access, label access, or canary correlation.
- Every representation can be traced back to the same Raw-G facts.
- A representation-oracle test proves the canonical renderings retain truth-relevant visible information.
- Any lossy transformation is declared and scientifically justified.

### Phase 7 - Baseline suite and common training harness

**Scope**

Implement all P-only and Raw-G baselines, a shared adapter interface, resource accounting, deterministic data loading, training, calibration, checkpointing, and pre-registered search.

**Files**

- `src/pead/baselines/{base,p_only,tabular,neural,sequence,graph,bayesian,policy,validator,judge,scalar,ensemble}.py`
- `src/pead/core/{training,calibration,budgets}.py`
- `configs/methods/{p_only_*,raw_g_*}.yaml`
- `manifests/method_cards/*.yaml`
- `scripts/train_suite.py`, `scripts/run_suite.py`, `scripts/audit_budget.py`
- `tests/integration/test_method_suite.py`

**Code and implementation method**

- Every method emits the same three-outcome `MethodDecision` schema.
- Implement every architecture, preprocessing pipeline, search grid, trial count, seed set, schedule, early-stopping rule, calibration method, compute ceiling, checkpoint tie-break, and failure condition exactly as registered in Section 5.1.1.
- Use matched training/calibration IDs inside each access profile.
- Record seeds, package versions, hardware, wall time, memory, calls/tokens, checkpoint hashes, and complete hyperparameter history.
- Fit calibration and terminal operating points only on the calibration split using the registered lexicographic objective.
- Threshold sweeps are reported but cannot replace the pre-registered headline operating point.
- Create and audit one fidelity method card per comparator; disclose MAVS human design effort separately from compute.
- Include the learned Oracle-G MLP as a non-headline representation/generator sanity comparator.

**Verification and completion gates**

- All 9 P-only and 12 Raw-G method families run through the same runner.
- GBDT, graph, scalar-risk, validator/policy, and ensemble comparators are not omitted.
- Judge/verifier model hash, prompt hashes, decoding, parser, cache, retry, call/token budget, and reproduction rule match the frozen contract.
- Every comparator has a complete method card with a valid fidelity class and claim boundary.
- Training is reproducible within registered deterministic/tolerance rules.
- Budget parity and equal-information audits pass.
- No development or public-validation metric can change holdout definitions.

### Phase 8 - Frozen MAVS-GC, DS-CF, and architectural ablations

**Scope**

Integrate original MAVS-GC, MAVS-GC + DS-CF, prediction-only MAVS, fixed and learned scalarized variants, and ablations A00-A15.

**Files**

- `src/pead/mavs/{adapter,governed_consensus,ds_cf,profiles,scalarization,ablations,traces}.py`
- `configs/methods/mavs_*.yaml`
- `configs/diagnostics/ds_cf_*.yaml`
- `tests/unit/test_ds_cf_invariants.py`
- `tests/integration/test_mavs_adapter.py`
- `tests/property/test_mavs_scope_and_veto.py`

**Code and implementation method**

- Keep specialist answer evidence separate from diagnostic condition evidence through authorization.
- Trace supports, diagnostic vector, severity, contextual weights, mitigation, threshold, veto, ambiguity, consensus, and terminal decision.
- Implement `z_c`, `z_h`, `z_s`, `z_m`, `z_p`, `z_o`, and `z_f` against the stable IDs, scope generators, authority limits, interactions, and monotonicity contracts frozen before Phase 4.
- Raw correlation alone cannot hard-veto; safe consistency cannot override a certified hard veto; mitigation remains bounded.
- All ablations retain identical Raw-G access. Learned scalarization uses the same training/calibration data and budget policy as comparable Raw-G learners.
- No MAVS module is importable from generators or label engines.

**Verification and completion gates**

- Original and DS-CF profiles are frozen and versioned.
- Implementation-to-registry audit proves every DS-CF signal matches its pre-Phase-4 semantic/version contract; any semantic change reopens Phases 0, 4, 8, and all dependent banks.
- Exhaustive/discretized rule-fidelity tests find zero registered veto violations.
- Scope, ambiguity, mitigation, monotonicity, and trace-completeness tests pass.
- The central scalar-compression test is executable on structural and domain holdouts.

### Phase 9 - Metrics, statistics, audits, failure cards, and report builders

**Scope**

Implement integrity, paradigm, protected-decision, Diagnostic Sciences, sequential, causal, statistical, and claim-eligibility metrics, plus the complete audit suite and report traceability.

**Files**

- `src/pead/metrics/{paradigm,protected,causal,scope,sequential,statistics}.py`
- `src/pead/audits/{equivalence,authorization,leakage,access,holdouts,budget,traces,abstention,manifest,reproduction,claims,failure_retention,non_triviality}.py`
- `src/pead/reports/{tables,figures,failure_cards,claim_ledger}.py`
- `src/pead/reports/failure_card_schema.py`
- `scripts/{audit_all,build_report}.py`
- `tests/unit/test_metrics_*.py`
- `tests/integration/test_master_audit.py`
- `tests/integration/test_failure_card_bijection.py`
- `results/audits/<run_id>/human/*.json`

**Code and implementation method**

- Compute LBG, GIG, GAG, AFA, UAR, FRR, escalation, terminal coverage, forced-certainty error, unnecessary escalation, catastrophic acceptance, worst-world, and worst-decile metrics.
- Compute every Diagnostic Sciences measure separately: in-scope sensitivity, scope-matched specificity, conditional perception extension, intended decision influence `I_in`, out-of-scope influence `I_out`, redundancy, nuisance signal/decision instability, pairwise harmful composition, set-level harmful composition, protected-error delta, escalation delta, scope leakage, and boundary discontinuity.
- Compute every sequential measure separately: reversal detection latency, stale-authorization rate, unsafe-continuation rate, recovery correctness, recovery latency, decision hysteresis, false-reversal sensitivity, and authorization-flip accuracy at the known change point.
- Use paired world/pair/sequence analysis; cluster bootstrap by evaluation unit and by mechanism/domain for generalization.
- Use exact binomial intervals for zero counts.
- Report per-domain/per-mechanism effects before macro averages.
- Apply multiple-comparison correction to secondary ablation families.
- Generate immutable strict-schema failure cards from Section 5.15 and enforce a bijection with qualifying events.
- Execute the signed human audit program in Section 5.14, including label engines, projection parity, stratified samples, failures/quarantines, non-triviality, baseline fidelity, and negative-result retention.

**Verification and completion gates**

- Metric unit tests include edge cases, empty denominators, zero counts, and known analytic fixtures.
- Known sequence and diagnostic fixtures reproduce every individual registered metric, including boundary discontinuity and false-reversal sensitivity.
- Failure-card bijection has zero missing, duplicate, orphaned, or schema-invalid cards.
- All mandatory human audit checkpoints have signed pass artifacts or release is blocked.
- Master audit returns nonzero for every release-blocking fixture.
- Report builder cannot suppress failed methods/cases or emit an ineligible claim.
- Every table/figure cell resolves to processed data, raw traces, config, and audit IDs.

### Phase 9A - Prebuild and seal claim-bearing holdout generators

**Scope**

Before any Phase 10 model training, calibration, or public-validation result is produced, design, implement, review, hash, sign, encrypt, and seal every scientifically substantive claim-bearing holdout component. No method behavior may influence the final challenge distribution.

**Files and artifacts**

- `configs/holdouts/{mechanisms,policy_forms,graph_topologies,scope_interactions,interventions,nuisance,domains,seeds,allocations}.yaml`
- `configs/tracks/near_distance_registry.yaml`
- `configs/allocations/final_claim_bank_v1.yaml`
- `src/pead/holdouts/{generator,allocator,packager,custody}.py`
- `manifests/custody/holdout_design_commitment.json`
- `manifests/custody/encrypted_blind_package.index.json`
- `results/audits/<preseal_id>/{holdout_design,allocation,custody,human_review}.json`

**Code and implementation method**

- Prebuild holdout mechanism families/compositions, policy logical forms, graph topology families, scope interactions, intervention classes, nuisance generators, all eight domain templates, exact hidden seed lists, generation code, ambiguity-proof rules, typed distances, and allocation/substitution rules.
- Apply the exact scale/sub-bank/epsilon/sequence/scope/evidence/control allocations in Section 5.9.
- Package content and labels separately using the custody protocol in Section 5.13.
- Commit only ciphertext, commitments, counts, nonrevealing allocation metadata, and hashes to the development repository.
- Obtain internal-independent review of scientific non-triviality, domain meaning, allocation, generator/label separation, and custody enforcement before sealing.

**Verification and completion gates**

- Every holdout design file and generator has a signed hash before Phase 10 begins.
- Exact hidden seed lists are encrypted and hash-committed; no training/development process can read them.
- Allocation, atomic-group, distance, ambiguity-certificate, generator-label-separation, and custody tests pass.
- The custody workspace demonstrates denial/logging of pre-freeze development access.
- `Path.md` and the remote Git commit prove Phase 9A predates all Phase 10 training and public-validation artifacts.
- Any later scientific holdout-design change requires a new study version and repeats Phase 9A before retraining.

### Phase 10 - Development banks, training, calibration, and public validation

**Scope**

Generate only the pre-registered open development/calibration/public-validation banks, train every trainable method under Section 5.1, run fixed methods, select operating points, perform public validation, power/effect-size checks, and create a method-freeze candidate. Claim-bearing holdout design is already complete and sealed; Phase 10 cannot change it.

**Files and artifacts**

- `banks/development/`, `banks/calibration/`, `banks/public_validation/`
- `results/raw/<dev_run_id>/`
- `results/processed/<dev_run_id>/`
- `results/audits/<dev_run_id>/`
- `results/reports/<dev_run_id>/`
- `manifests/freeze_candidate_v1.json`

**Code and implementation method**

- Use exactly the open-bank volumes in Section 5.1.2 and group-atomic partitions.
- Before the first training command, verify the Phase 9A design-commitment signature and record it in every training trace.
- Run every trainable method within its exact architecture, data, trial, seed, schedule, calibration, and compute budget.
- Infrastructure defects may be fixed; each fix invalidates and regenerates affected artifacts.
- Scientific underperformance is retained.
- Select thresholds on calibration only.
- Freeze report templates, statistical procedures, minimum effect sizes, and primary architecture-specific advantage before the blind run.

**Verification and completion gates**

- No sealed/final-bank access occurs.
- Phase 9A holdout commitments remain byte-identical throughout Phase 10.
- All public-validation integrity gates pass.
- Leakage, duplicate, budget, parity, non-triviality, and abstention audits pass.
- Power/effect-size report justifies claim-bearing sample sizes.
- Freeze candidate includes every claim-relevant file hash.

### Phase 11 - Method freeze, precommitment verification, and bank unlock

**Scope**

Verify the already precommitted holdout hashes; freeze methods, checkpoints, operating points, environments, metrics, audits, and report code; unlock/materialize the already-designed encrypted bank; and execute contamination/custody checks. Nothing scientifically substantive is designed in this phase.

**Files and artifacts**

- `banks/sealed/structural/`
- `banks/sealed/domains/`
- `banks/sealed/final_blind/`
- `manifests/custody/holdout_design_commitment.json`
- `manifests/freeze_manifest.json`
- `manifests/blind_bank_manifest.json`
- `results/audits/<freeze_id>/{holdout_hash,contamination,custody_unlock}.json`

**Code and implementation method**

- Verify every Phase 9A mechanism, grammar, topology, interaction, intervention, nuisance, domain-template, seed-list, generator, allocation, distance, and ambiguity-proof hash without modification.
- Freeze and sign code, configs, environment, truth engines, projections, metrics, audits, methods, checkpoints, hyperparameters, prompts, operating points, and report templates.
- Submit the signed freeze manifest to the custody process; unlock and one-shot materialize the precommitted ciphertext.
- Cross-check materialized content hashes/counts/allocations against Phase 9A commitments.
- Keep labels encrypted separately and expose only registered projections to method processes.
- Run duplicate/overlap/contamination and access-log audits before blind execution.

**Verification and completion gates**

- Nearest-neighbor/structural/graph duplicate audit finds no prohibited overlap.
- Training, calibration, and final template/grammar/topology registries are disjoint by construction and by hash.
- Phase 9A and Phase 11 design hashes match exactly; any mismatch blocks unlock and invalidates the study version.
- Blind-custody tests prove the bank was inaccessible before the signed method freeze and every access was logged.
- Freeze manifest is complete and signed.
- No scientifically substantive holdout file is created or changed in Phase 11.
- Any post-precommit holdout-design change or post-freeze method/report change creates a new study version.

### Phase 12 - One-pass blind evaluation and brutal generalization audit

**Scope**

Unlock the sealed bank, execute all valid methods once, audit before aggregate inspection, classify incidents, and retain all scientific outcomes.

**Files and artifacts**

- `results/raw/<blind_run_id>/`
- `results/processed/<blind_run_id>/`
- `results/audits/<blind_run_id>/`
- `results/reports/<blind_run_id>/`
- `results/manifests/<blind_run_id>/`
- `Path.md` incident and adjudication entries

**Code and implementation method**

- Verify signed freeze and bank seals before execution.
- Commit every decision before hidden-label reveal.
- Use the custody stream: evaluator receives encrypted case facts, method receives projection only, and label is revealed only after decision/trace commitment.
- Execute matched methods on exact, near, reversal, scope, evidence, structural, and domain holdouts.
- Run leakage, access, trace, budget, holdout, abstention, failure-retention, non-triviality, and manifest audits before aggregate author inspection where practical.
- Classify events as infrastructure, contamination, or scientific. Only infrastructure defects permit a documented invalidation and complete affected-suite rerun.

**Verification and completion gates**

- No post-freeze parameter, feature, threshold, or representation changes.
- Every release-blocking audit passes.
- P-only lower-bound/error-coverage results, Raw-G escape, MAVS-vs-Raw-G, scalar compression, scope leakage, reversal fidelity, ambiguity, domain transfer, and worst-world results are all reported.
- Every failure and negative outcome is retained.
- Invalidated run IDs remain referenced and cannot be mistaken for valid release runs.

### Phase 13 - Evidence package, clean reproduction, and bounded release

**Scope**

Build the public evidence package, regenerate all tables/figures, run clean-checkout reproduction, generate claim eligibility, and perform the final causal-rejection and completeness audits.

**Files and artifacts**

- `CLAIM_ELIGIBILITY.md`, `REPRODUCE.md`
- `results/reports/<release_run_id>/`
- `results/audits/<release_run_id>/master_audit.json`
- `manifests/final_release.json`
- public case banks/traces according to the release policy
- failure cards, invalidation ledger, and artifact-to-claim map
- baseline method cards and MAVS human-design-cost disclosure
- signed human-audit package

**Code and implementation method**

- Rebuild deterministic banks and processed results from a clean checkout and locked environment.
- Distinguish exact hashes from frozen model-output tolerance checks.
- Generate claim language automatically from passed outcome tiers.
- Package code, configs, environment lock, manifests, banks, traces, processed results, audits, failures, claim ledger, and regeneration commands.
- Publish baseline fidelity classes and prohibit proxy/adaptation claims from being described as official reproductions.
- Publish the limitations of internal separately prompted review and do not represent it as external validation.

**Verification and completion gates**

- Every headline result resolves to raw traces and passed audits.
- Clean reproduction matches signed expectations and preserves all conclusions.
- All failed methods, errors, quarantines, and negative results remain visible.
- Every qualifying failure has exactly one strict failure card and every mandatory human checkpoint has a signed artifact.
- Causal-rejection closure and final delivery checklist pass.
- `Path.md` records the final run identity, reproduction identity, deviations, and release verdict.

## 7. Phase dependency and reopening rules

```text
0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 9A -> 10 -> 11 -> 12 -> 13
         \---------------- truth ----------------/  \preseal/ \train/ \freeze/ \release/
```

- Phase 2 truth defects reopen Phases 2-13.
- Phase 3/4 bank defects reopen the affected generator phase and Phases 9A-13.
- Phase 5 domain defects reopen the affected adapter, holdout selection, and Phases 9A-13.
- Phase 6 access defects invalidate affected method results and reopen Phases 6-13.
- Phase 7/8 method defects after freeze require a new study version unless they are proven interface-only infrastructure defects and the complete affected blind suite is invalidated and rerun.
- Phase 9 metric/audit defects reopen every claim that depends on them.
- Any Phase 9A scientific holdout-design change invalidates its commitment and requires a new study version before Phase 10 retraining.
- Phase 10 may not begin without a remotely published Phase 9A commitment whose timestamp predates every training/public-validation artifact.
- Any Phase 11 commitment mismatch, custody failure, contamination, or post-freeze tuning invalidates the generalization claim and blind run.
- A Phase 13 reproduction mismatch blocks the release claim even if scientific results are favorable.

## 8. Canonical commands

Commands will be finalized against the implemented CLI, but the required interfaces are:

```bash
python scripts/clear_results.py --scope pead --dry-run
python scripts/clear_results.py --scope pead --confirm
python scripts/validate_config.py --study configs/study/pead_main_v1.yaml
python -m pytest tests/unit tests/property tests/metamorphic -q
python -m pytest tests/integration tests/blind_contract -q
python -m compileall -q src scripts tests
python scripts/generate_bank.py --study configs/study/pead_main_v1.yaml --split development
python scripts/preseal_holdouts.py --study configs/study/pead_main_v1.yaml --custody-workspace <SEALED_WORKSPACE>
python scripts/train_suite.py --study configs/study/pead_main_v1.yaml
python scripts/run_suite.py --study configs/study/pead_main_v1.yaml --split public_validation
python scripts/freeze_study.py --study configs/study/pead_main_v1.yaml
python scripts/unlock_blind_bank.py --freeze-manifest manifests/freeze_manifest.json --custody-workspace <SEALED_WORKSPACE>
python scripts/run_blind_suite.py --freeze-manifest manifests/freeze_manifest.json
python scripts/audit_all.py --study configs/study/pead_main_v1.yaml --run-id <RUN_ID> --strict
python scripts/build_report.py --run-id <RUN_ID>
python scripts/reproduce_all.py --manifest manifests/final_release.json
```

## 9. Specification coverage matrix

Coverage is clause-level, not section-level. Phase 0 creates `configs/requirements/pead_v1_requirements.yaml` by extracting every normative bullet, table row, appendix field, metric, audit, gate, and stop condition from the source DOCX into one stable ID. The registry schema requires: exact source clause, phase, files, tests, produced artifact, release-failure condition, and affected claim. A source-to-registry count/hash audit blocks Phase 0 if any clause is absent, duplicated, or represented only by its parent heading.

The matrix below is the human-readable control index. The machine registry expands inventory ranges such as M01-M12, A00-A15, record fields, and audit rows to one entry per source row/field.

| Requirement ID | Exact requirement | Phase | Files | Test/audit | Produced artifact | Release failure / claim affected |
|---|---|---:|---|---|---|---|
| CTRL-001 | H1 information necessity and H2 architecture value remain separate | 0, 9, 13 | `CLAIMS.md`, claim rules | claim dependency test | claim ledger | Merge/overclaim blocks C2-C4 |
| CTRL-002 | Negative scientific outcomes are retained; integrity failures invalidate | 0, 9, 12, 13 | study config, report builder | failure-retention audit | outcome ledger | Selective reporting blocks release |
| CTRL-003 | Self-Learning MAVS excluded from Paper 1 | 0, 4, 13 | claim config | method/claim scan | paper-boundary report | Blocks Paper 1 claim |
| CTRL-004 | Every phase has tests, audits, `Path.md`, commit, push, remote verification | all | `WorkPlan.md`, `Path.md` | phase-close audit | remote commit record | Phase remains incomplete |
| CORE-001 | Content IDs, seeds, hashes, configs, immutable runs | 1 | `src/pead/core/*` | deterministic/property tests | core audit | Blocks all results |
| CORE-002 | Canonical key order, UTF-8, float, graph/set and action normalization | 1 | `hashing.py` | canonicalization tests | hash report | PEI/reproduction invalid |
| CORE-003 | Trace contains study/run/config/commit/environment/world/group/split/method/budget/projection/decision/resource/label-order fields | 1, 6 | `traces.py` | trace schema test | trace-completeness report | Blocks headline results |
| CORE-004 | Decision commits before hidden-label reveal | 1, 11, 12 | runner/custody | order/commit audit | signed event log | Blocks affected run |
| GEN-001 | Generators emit facts/surface/lineage/interventions, never labels | 3 | `src/pead/world/*` | source/dependency/schema scan | generator separation report | Invalidates study version |
| GEN-002 | Surface templates and authorization logic are separate and label-swappable | 3, 5 | world/domain templates | label-swap metamorphic tests | shortcut report | Quarantine bank |
| GEN-003 | Pair intervention proof names changed authorization and unchanged predictive parents | 3 | `exact.py` | twin invariance | intervention certificate | Blocks pair/bank |
| GEN-M01 | Authority mismatch mechanism | 3, 5 | mechanisms/domains | permission twin/reversal tests | M01 bank report | C1-C3 affected |
| GEN-M02 | Policy conflict mechanism | 3, 5 | mechanisms/policies | policy composition tests | M02 bank report | C1-C3 affected |
| GEN-M03 | Provenance dependence mechanism | 3, 5 | graph mechanisms | topology/source tests | M03 bank report | C1-C5 affected |
| GEN-M04 | Evidence masking mechanism | 3, 4 | mechanisms/evidence | ambiguity/witness tests | M04 bank report | C3/C6 affected |
| GEN-M05 | Reversibility shift mechanism | 3, 4 | mechanisms/reversal | rollback tests | M05 report | C1-C3 affected |
| GEN-M06 | Consequence escalation mechanism | 3, 5 | mechanisms/domains | consequence tests | M06 report | protected claims |
| GEN-M07 | Temporal validity mechanism | 3, 4 | mechanisms/reversal | expiry/restore tests | M07 report | C1-C3 affected |
| GEN-M08 | Shared premise corruption mechanism | 3, 8 | mechanisms/DS-CF | shared-fault tests | M08 report | C4/C5 affected |
| GEN-M09 | Counterfactual fragility mechanism | 3, 8 | mechanisms/DS-CF | view-permission tests | M09 report | C4/C5 affected |
| GEN-M10 | Constraint interaction mechanism | 3, 5 | mechanisms/policies | >=3-factor tests | M10 report | non-triviality/C4 |
| GEN-M11 | Scope boundary mechanism | 3, 4 | scope generators | out-of-scope invariance | M11 report | C5 affected |
| GEN-M12 | Ambiguity mechanism | 2-4 | ambiguity/evidence | complete proof tests | M12 certificates | C6 affected |
| LABEL-001 | Declarative DSL supports typed/logical/temporal/graph/consequence/evidence/ambiguity rules | 2 | `src/pead/labels/*` | DSL fixtures | DSL audit | Blocks labels |
| LABEL-002 | Procedural evaluator shares no decision code/parser | 2 | `evaluator_reference.py` | dependency/fixture tests | independence report | Invalidates labels |
| LABEL-003 | Dual engines agree on 100% of released cases | 2, 9 | label audit | full agreement audit | L-01 report | Blocks release |
| LABEL-004 | Oracle rule evaluator is 100% on valid fixtures | 2 | evaluator DSL | oracle fixtures | oracle report | Blocks generator sanity |
| LABEL-005 | Claim-bearing ambiguity uses complete proof, never sampling alone | 2, 4 | ambiguity solver | certificate verifier | ambiguity certificates | Blocks C6/case |
| TRACK-I-A | Accept/Reject exact bank: 800 pairs/domain, balanced orientation | 3, 9A | allocation/exact | quota/PEI/ADI | I-A manifest | Blocks C1/C2 |
| TRACK-I-B | Accept/Escalate exact bank: 400 pairs/domain | 2, 3, 9A | allocation/exact | quota/certificate | I-B manifest | Blocks three-action/C6 |
| TRACK-I-C | Reject/Escalate exact bank: 400 pairs/domain | 2, 3, 9A | allocation/exact | quota/witness/certificate | I-C manifest | Blocks three-action/C6 |
| TRACK-I-N | Same-label exact controls: 400 pairs/domain | 3, 9A | allocation/exact | invariance/quota | I-N manifest | Blocks shortcut claims |
| TRACK-I-LB | Deterministic, randomized, escalate-both, pair error-coverage lower bound | 3, 9, 12 | exact/paradigm metrics | analytic/pair tests | lower-bound report | Blocks C2 |
| SPLIT-001 | Pair/sequence/latent/template/intervention/provenance lineage split atomically | 3, 9A | allocator | group-overlap audit | split manifest | Contamination blocks claims |
| TRACK-II-001 | Typed scalar/vector/category/set/graph/probability/text/missing distances | 3, 9A | distances/registry | metric fixtures | distance registry report | Blocks near bank |
| TRACK-II-002 | Eight epsilons x 125 pairs/domain with fixed suballocation | 3, 9A | near allocation | quota/distance audit | near manifest | Blocks robustness claim |
| TRACK-III-001 | Permission/policy/provenance/rollback/expiry/evidence reversals | 4 | `reversal.py` | transition tests | sequence bank | Blocks reversal claim |
| TRACK-III-002 | Detection latency, stale rate, unsafe continuation, recovery correctness/latency, hysteresis, false sensitivity, flip accuracy | 9, 12 | sequential metrics | known-sequence fixtures | sequential report | Blocks Track III claim |
| DIAG-REG-001 | Registry exists before Phase 4 with scope/generator/authority/interaction/version fields | 0, 1 | diagnostics/core registry | registry schema test | registry manifest | Phase 4 blocked |
| DIAG-ZC | `z_c` correlation presence has no independent veto | 0, 4, 8 | DSCF-ZC config/code | scope/veto tests | diagnostic card | C5/C4 affected |
| DIAG-ZH | `z_h` harmful correlation is witness-conditioned | 0, 4, 8 | DSCF-ZH config/code | composition tests | diagnostic card | C5/C4 affected |
| DIAG-ZS | `z_s` safe consistency is bounded mitigation | 0, 4, 8 | DSCF-ZS config/code | veto-dominance tests | diagnostic card | C5/C4 affected |
| DIAG-ZM | `z_m` missing evidence is danger/ambiguity witness | 0, 4, 8 | DSCF-ZM config/code | masking tests | diagnostic card | C5/C6 affected |
| DIAG-ZP | `z_p` policy conflict is scope-bound witness | 0, 4, 8 | DSCF-ZP config/code | policy-scope tests | diagnostic card | C5 affected |
| DIAG-ZO | `z_o` overconfidence is soft, nonterminal evidence | 0, 4, 8 | DSCF-ZO config/code | authority tests | diagnostic card | C5 affected |
| DIAG-ZF | `z_f` fragility uses only permitted alternate views | 0, 4, 8 | DSCF-ZF config/code | view-access tests | diagnostic card | C5 affected |
| TRACK-IV-001 | Positive/matched-negative/boundary/out-of-scope banks, 100 each/diagnostic/domain | 4, 9A | scope allocation | quota/scope tests | scope manifest | Blocks C5 |
| TRACK-IV-002 | Composition and nuisance controls evaluate interactions/stability | 4, 9 | scope metrics | pairwise/set tests | composition report | Blocks C5/C4 |
| TRACK-V-001 | Resolvable, reducibly ambiguous, irreducibly ambiguous, 500/class/domain | 2, 4, 9A | evidence allocation | certificate/quota audit | evidence manifest | Blocks C6 |
| DOMAIN-001 | Eight named bounded proxy adapters share one contract | 5 | `src/pead/domains/*` | schema parity | domain registry | Blocks broad claim |
| DOMAIN-002 | Six mechanisms/domain; graph/time/policy/composition/ambiguity minima | 5, 9A | domains/configs | non-triviality audit | domain review | Blocks domain |
| DOMAIN-003 | Two complete unseen domains fixed before training | 5, 9A | domain holdout config | contamination audit | sealed templates | Blocks generalized claim |
| ACCESS-001 | P-only/Raw-G/Oracle-G visibility profiles | 6 | projections/access configs | field-mask tests | access manifest | Blocks H1/H2 |
| ACCESS-002 | Projection-only transformation; no WorldState back-reference | 6 | firewall | static/runtime tests | access audit | Invalidates method results |
| ACCESS-003 | Canary, forbidden import/attribute/label access tests | 6, 9 | firewall/audit | adversarial access tests | canary report | Blocks release |
| ACCESS-004 | Canonical tabular/sequence/graph Raw-G semantic parity | 6, 7 | renderings | field-method matrix | parity report | Blocks H2 |
| METHOD-001 | Every trainable method follows exact Section 5.1.1 specification | 7, 10 | methods/configs | config/budget audit | training manifest | Method invalid |
| METHOD-002 | Judge identity/prompt/decoding/budget/retry/parser/cache frozen | 7, 10 | judge config/card | request replay | judge manifest | Judge invalid |
| METHOD-003 | Method cards classify fidelity and limitations | 7, 13 | method cards | schema/human audit | fidelity appendix | Comparator claim blocked |
| METHOD-004 | MAVS human design effort separate from compute | 7, 13 | resource report | disclosure audit | cost appendix | Fairness claim blocked |
| METHOD-005 | Learned Oracle-G sanity comparator is non-headline | 7, 10 | oracle config | representation sanity | oracle learned report | Interface validity blocked |
| MAVS-A00-A15 | Every ablation in Section 5.6 uses registered identical access and causal change | 8, 12 | mavs/ablations configs | ablation/access audit | ablation matrix | C4 limited/blocked |
| MAVS-SCALAR | Fixed and learned one-scalar reductions are central architecture tests | 7, 8, 12 | scalar configs | holdout frontier | scalar report | Strong C4 blocked |
| ALLOC-001 | Exact 16k, near 8k, reversal 4k/24k steps, scope 22.4k, evidence 12k | 9A, 12 | allocation manifest | exact-count audit | signed allocation | Claim bank invalid |
| ALLOC-002 | >=20% matched controls; prior shift and label permutation | 3, 9A | control allocations | quota/prior audit | control manifest | Leakage/robustness blocked |
| ALLOC-003 | Domain/mechanism/label/intervention/complexity denominators present | 9A, 9 | allocations/metrics | balance audit | denominator report | Protected claims blocked |
| HOLD-001 | All substantive holdout design signed in Phase 9A before Phase 10 | 9A | holdout configs/code | chronology/hash audit | design commitment | Study version invalid |
| HOLD-002 | Phase 11 only verifies/freezes/unlocks/materializes/checks contamination | 11 | freeze/custody scripts | no-design diff audit | unlock report | Blind run blocked |
| HOLD-003 | Encrypted separate custody, key isolation, one-shot materialization, logged access | 9A, 11, 12 | custody code/protocol | custody attack tests | signed custody log | Bank invalid |
| HOLD-004 | Labels encrypted until decision/trace commitment; methods see projection only | 11, 12 | custody/runner | reveal-order audit | event log | Run invalid |
| METRIC-INT | PEI, ADI, label agreement, trace completeness, access compliance, reproduction | 9, 12, 13 | integrity metrics | exact fixtures | integrity report | Release blocked |
| METRIC-PAR | LBG, GIG, GAG, AFA and raw components | 9, 12 | paradigm metrics | analytic fixtures | paradigm report | C2-C4 blocked |
| METRIC-PROT | UAR, FRR, escalation, coverage, forced certainty, unnecessary escalation, catastrophic/worst losses | 9, 12 | protected metrics | denominator/edge tests | protected report | Safety wording blocked |
| METRIC-DS | Sensitivity, specificity, CPE, I_in, I_out, redundancy, instability, compositions, deltas, leakage, discontinuity | 9, 12 | scope metrics | diagnostic fixtures | DS report | C5 blocked |
| METRIC-STAT | Pair/sequence paired analysis, clustered bootstrap, exact zero intervals, strata, multiplicity | 9, 12 | statistics | synthetic known estimates | statistics report | Effect claim blocked |
| AUDIT-LEAK | Linear, GBDT, sequence, graph, nearest-neighbor leakage adversaries | 3, 9, 10-12 | leakage audit | permutation bands | leakage report | Bank quarantined |
| AUDIT-FAIR | Semantic information and budget parity; lossy transforms declared | 6, 7, 9 | parity/budget audit | field-method test | fairness report | C4 blocked |
| AUDIT-NTRIV | Composition/time/graph/scope/ambiguity/domain/near minima | 5, 9, 9A | non-triviality audit | bank inspection | non-triviality report | Broad claim blocked |
| AUDIT-HUM | Signed reviews of engines/projection/strata/failures/quarantines/parity/non-triviality/negative results | 5, 9, 12, 13 | human audit artifacts | completeness audit | signed review package | Release blocked |
| FAIL-001 | Strict failure-card fields and qualifying-event bijection | 9, 12, 13 | failure-card schema/audit | bijection test | failure-card bank | Selective reporting blocked |
| FREEZE-001 | Methods/checkpoints/prompts/thresholds/metrics/reports frozen before unlock | 11 | freeze manifest | hash verification | signed freeze | Blind run blocked |
| BLIND-001 | One scientific blind run; only documented infrastructure repair permits full invalidated rerun | 12 | blind runner/adjudication | incident audit | blind-run ledger | Retuning invalidates |
| REPRO-001 | Clean checkout recreates deterministic artifacts and conclusion-preserving model outputs | 13 | reproduce scripts/lock | clean rebuild | reproduction report | Repro claim/release blocked |
| CLAIM-001 | Claim eligibility generated from audits and outcome tiers with forbidden wording | 9, 13 | claim ledger | eligibility tests | `CLAIM_ELIGIBILITY.md` | Overclaim blocks release |
| APP-A-PAIR-01..12 | Every PairRecord field: IDs, hashes, distance, intervention/proof, labels/reasons, split, leakage audit | 1, 3 | types/schema | field/schema tests | data dictionary | Missing field blocks bank |
| APP-A-SCOPE-01..10 | Every ScopeContract field: diagnostic, family/context/response/influence, four generators, monotonicity | 0, 1, 4 | diagnostic registry | registry tests | data dictionary | Scope bank blocked |
| APP-A-METHOD-01..08 | Every MethodDecision field: decision/scores/operating point/rationale/trace/resources/projection/commit time | 1, 6, 7 | method schema | trace tests | data dictionary | Method result blocked |
| APP-B-001 | Blind execution verifies freeze/seal, projection, commit-before-reveal, strict audit | 11, 12 | blind runner | blind-contract test | blind trace | Run invalid |
| APP-B-002 | Lower-bound analysis is pair-level and bootstrapped by pair/domain/mechanism | 3, 9, 12 | paradigm metrics | analytic test | lower-bound report | C2 blocked |
| APP-B-003 | Claim C2/C4 eligibility follows exact registered predicates | 9, 13 | claims audit | eligibility fixture | claim map | Claim blocked |
| APP-C-UNIT | Serialization, DSL, reference evaluator | 1, 2 | unit tests | CI | test report | Phase blocked |
| APP-C-PROP | Twin invariance, authorization monotonicity, scope safety | 2-4 | property tests | CI | test report | Phase blocked |
| APP-C-META | Nuisance invariance and relevant-intervention fidelity | 3-5 | metamorphic tests | CI | test report | Phase blocked |
| APP-C-INT | Access, method suite, MAVS adapter, blind contract | 6-12 | integration tests | CI | test report | Phase/run blocked |
| APP-C-STRESS | Millions of decisions without trace loss, collision, nondeterminism | 1, 10 | stress tests | scale test | stress report | Scale claim blocked |
| APP-C-REPRO | Fresh environment regenerates artifacts and conclusions | 13 | reproduction | clean test | repro report | Release blocked |
| APP-D-001 | Study/source/generator/label/bank/method/trace/audit/result/claim/failure/reproduction identities | 0, 9A, 11-13 | manifests | manifest completeness | final manifest | Release blocked |
| STOP-01..07 | Exact mismatch, label disagreement, forbidden access, contamination/tuning, missing lineage, repro change, MAVS-coupled truth | 2, 3, 6, 9A-13 | master audit | stop-condition fixtures | stop report | Immediate stop/invalidation |

The machine registry must expand every `..` range above to individual IDs and retain the exact source text. `audit_requirements.py` compares source extraction count/hash, registry entries, implemented files, tests, artifacts, and master-audit results. A requirement cannot be marked covered by a parent/range row alone.

## 10. Definition of done

The project is complete only when:

1. All phases are closed in `Path.md` with commands and evidence.
2. No mandatory specification item is marked prose-only.
3. All integrity gates pass on the release run.
4. Claim-bearing benchmarks are structurally and domain-wise different from training and calibration.
5. Every trained model has been evaluated on the complete applicable independent holdout battery.
6. H1 and H2 are reported separately and honestly, including negative outcomes.
7. Every number, failure, deviation, invalidation, and artifact is traceable.
8. A clean checkout reproduces deterministic artifacts and conclusion-preserving model results.
9. Only the new, manifest-identified PEAD release results are present in the release package.
10. Phase 9A's signed scientific holdout design predates every model-training, calibration-result, and public-validation artifact, and Phase 11 changed none of it.
11. The custody log proves pre-freeze inaccessibility, key isolation, one-shot materialization, projection-only method access, and decision-before-label reveal.
12. The clause-level requirements audit has no missing, duplicate, prose-only, untested, or artifact-free normative requirement.
13. Exact, near, reversal, scope, evidence, diagnostic, baseline-fidelity, human-review, and failure-card allocation/schema audits all pass.
