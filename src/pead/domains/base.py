"""Universal protocol for open PEAD domain adapters."""

from __future__ import annotations

from abc import ABC
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from pead.core.config import load_config
from pead.core.hashing import canonical_hash
from pead.core.types import deep_freeze


class DomainContractError(ValueError):
    """Raised when a domain adapter violates the universal contract."""


TERMINAL_TOKENS = frozenset(
    {"accept", "accepted", "reject", "rejected", "escalate", "authorized"}
)
OBVIOUS_AUTHORIZATION_FIELDS = frozenset(
    {
        "allow",
        "allowed",
        "approval",
        "approved",
        "authorization",
        "authorized",
        "decision",
        "deny",
        "denied",
        "is_authorized",
        "terminal_action",
    }
)
MECHANISM_KINDS = frozenset(
    {"atomic", "composition", "ambiguity", "graph", "temporal", "policy_grammar"}
)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainContractError(f"{field} must be non-empty text")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DomainContractError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DomainContractError(f"{field} must be a sequence")
    return value


@dataclass(frozen=True)
class MechanismContract:
    mechanism_id: str
    kind: str
    semantic_name: str
    description: str
    governance_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in MECHANISM_KINDS:
            raise DomainContractError(f"unsupported mechanism kind: {self.kind}")
        if not self.governance_paths:
            raise DomainContractError("mechanism requires governance paths")


@dataclass(frozen=True)
class DomainDefinition:
    schema_version: str
    domain_id: str
    adapter_id: str
    semantic_name: str
    author_id: str
    task_objective: str
    task_fields: tuple[str, ...]
    candidate_action_type: str
    candidate_fields: tuple[str, ...]
    predictive_fields: tuple[str, ...]
    raw_governance_fields: tuple[str, ...]
    mechanisms: tuple[MechanismContract, ...]
    graph_dependent: bool
    temporal_reversal: bool
    policy_grammar_composition: bool
    label_swaps: tuple[Mapping[str, Any], ...]
    surface_transforms: tuple[Mapping[str, Any], ...]
    proxy_scope: str
    proxy_exclusions: tuple[str, ...]
    cases_per_mechanism: int
    config_sha256: str

    def __post_init__(self) -> None:
        kinds = {item.kind for item in self.mechanisms}
        if self.schema_version != "1.0" or self.domain_id not in {
            f"D{index}" for index in range(1, 7)
        }:
            raise DomainContractError("open definition requires D1-D6 schema 1.0")
        if (
            len(self.mechanisms) < 6
            or "composition" not in kinds
            or "ambiguity" not in kinds
        ):
            raise DomainContractError(
                "open domain requires six mechanisms, composition, and ambiguity"
            )
        if self.cases_per_mechanism < 100:
            raise DomainContractError("anti-triviality denominator is below 100")
        if len(self.label_swaps) < 2 or len(self.surface_transforms) < 4:
            raise DomainContractError("anti-shortcut transform minima are unmet")
        lowered = {field.lower() for field in self.raw_governance_fields}
        if lowered & OBVIOUS_AUTHORIZATION_FIELDS:
            raise DomainContractError("Raw-G exposes an obvious authorization field")
        if len(self.raw_governance_fields) < 6:
            raise DomainContractError("Raw-G requires distributed governance evidence")
        sequences = (
            self.task_fields,
            self.candidate_fields,
            self.predictive_fields,
            self.raw_governance_fields,
        )
        if any(len(values) != len(set(values)) for values in sequences):
            raise DomainContractError("domain field identities must be unique")
        if len({item.mechanism_id for item in self.mechanisms}) != len(
            self.mechanisms
        ):
            raise DomainContractError("mechanism identities must be unique")
        if (
            self.graph_dependent != ("graph" in kinds)
            or self.temporal_reversal != ("temporal" in kinds)
            or self.policy_grammar_composition != ("policy_grammar" in kinds)
        ):
            raise DomainContractError(
                "capability declarations must match executable mechanism kinds"
            )

    @property
    def definition_hash(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class DomainTask:
    schema_version: str
    task_id: str
    domain_id: str
    objective: str
    observable_context: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "observable_context", deep_freeze(self.observable_context))


@dataclass(frozen=True)
class DomainCandidate:
    schema_version: str
    candidate_id: str
    action_type: str
    parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", deep_freeze(self.parameters))


@dataclass(frozen=True)
class DomainMechanism:
    schema_version: str
    mechanism_id: str
    kind: str
    governing_facts: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "governing_facts", deep_freeze(self.governing_facts))


@dataclass(frozen=True)
class DomainProjection:
    schema_version: str
    task_projection: Mapping[str, Any]
    candidate_projection: Mapping[str, Any]
    predictive_projection: Mapping[str, Any]
    raw_governance_projection: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in (
            "task_projection",
            "candidate_projection",
            "predictive_projection",
            "raw_governance_projection",
        ):
            object.__setattr__(self, name, deep_freeze(getattr(self, name)))
        raw = canonical_hash(self.raw_governance_projection).lower()
        if any(token in raw for token in TERMINAL_TOKENS):
            raise DomainContractError("projection contains a terminal shortcut")

    @property
    def schema_signature(self) -> tuple[tuple[str, str], ...]:
        return (
            ("task_projection", "mapping"),
            ("candidate_projection", "mapping"),
            ("predictive_projection", "mapping"),
            ("raw_governance_projection", "mapping"),
        )


@dataclass(frozen=True)
class DomainCase:
    schema_version: str
    case_id: str
    domain_id: str
    task: DomainTask
    candidate: DomainCandidate
    mechanism: DomainMechanism
    projection: DomainProjection
    surface: Mapping[str, Any]
    label_swap_id: str
    surface_transform_id: str
    latent_meaning_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface", deep_freeze(self.surface))

    @property
    def surface_hash(self) -> str:
        return canonical_hash(self.surface)


def definition_from_mapping(
    data: Mapping[str, Any],
    config_sha256: str,
) -> DomainDefinition:
    required = {
        "schema_version",
        "domain_id",
        "adapter_id",
        "semantic_name",
        "author_id",
        "task",
        "candidate",
        "projection",
        "mechanisms",
        "capabilities",
        "anti_shortcut",
        "bounded_proxy_claim",
        "validation",
    }
    if set(data) != required:
        raise DomainContractError("domain configuration fields are not exact")
    task = _mapping(data["task"], "task")
    candidate = _mapping(data["candidate"], "candidate")
    projection = _mapping(data["projection"], "projection")
    capabilities = _mapping(data["capabilities"], "capabilities")
    anti = _mapping(data["anti_shortcut"], "anti_shortcut")
    claim = _mapping(data["bounded_proxy_claim"], "bounded_proxy_claim")
    validation = _mapping(data["validation"], "validation")
    mechanisms = tuple(
        MechanismContract(
            mechanism_id=_text(item.get("mechanism_id"), "mechanism_id"),
            kind=_text(item.get("kind"), "mechanism kind"),
            semantic_name=_text(item.get("semantic_name"), "mechanism semantic_name"),
            description=_text(item.get("description"), "mechanism description"),
            governance_paths=tuple(
                _text(path, "governance path")
                for path in _sequence(item.get("governance_paths"), "governance_paths")
            ),
        )
        for item in (
            _mapping(raw, "mechanism")
            for raw in _sequence(data["mechanisms"], "mechanisms")
        )
    )
    return DomainDefinition(
        schema_version=_text(data["schema_version"], "schema_version"),
        domain_id=_text(data["domain_id"], "domain_id"),
        adapter_id=_text(data["adapter_id"], "adapter_id"),
        semantic_name=_text(data["semantic_name"], "semantic_name"),
        author_id=_text(data["author_id"], "author_id"),
        task_objective=_text(task.get("objective"), "task objective"),
        task_fields=tuple(
            _text(item, "task field")
            for item in _sequence(task.get("observable_fields"), "task fields")
        ),
        candidate_action_type=_text(candidate.get("action_type"), "candidate action"),
        candidate_fields=tuple(
            _text(item, "candidate field")
            for item in _sequence(candidate.get("parameter_fields"), "candidate fields")
        ),
        predictive_fields=tuple(
            _text(item, "predictive field")
            for item in _sequence(
                projection.get("predictive_fields"),
                "predictive fields",
            )
        ),
        raw_governance_fields=tuple(
            _text(item, "governance field")
            for item in _sequence(
                projection.get("raw_governance_fields"),
                "raw governance fields",
            )
        ),
        mechanisms=mechanisms,
        graph_dependent=capabilities.get("graph_dependent") is True,
        temporal_reversal=capabilities.get("temporal_reversal") is True,
        policy_grammar_composition=(
            capabilities.get("policy_grammar_composition") is True
        ),
        label_swaps=tuple(
            _mapping(item, "label swap")
            for item in _sequence(anti.get("label_swaps"), "label swaps")
        ),
        surface_transforms=tuple(
            _mapping(item, "surface transform")
            for item in _sequence(
                anti.get("surface_transforms"),
                "surface transforms",
            )
        ),
        proxy_scope=_text(claim.get("scope"), "proxy scope"),
        proxy_exclusions=tuple(
            _text(item, "proxy exclusion")
            for item in _sequence(claim.get("exclusions"), "proxy exclusions")
        ),
        cases_per_mechanism=int(validation.get("cases_per_mechanism", 0)),
        config_sha256=config_sha256,
    )


class DomainAdapter(ABC):
    """Shared task, candidate, mechanism, projection, and validation protocol."""

    CONFIG_FILE: ClassVar[str]
    EXPECTED_DOMAIN_ID: ClassVar[str]

    def __init__(self, repo_root: Path) -> None:
        loaded = load_config(repo_root, Path("configs/domains") / self.CONFIG_FILE)
        self.repo_root = repo_root
        self.definition = definition_from_mapping(
            loaded.data,
            loaded.canonical_sha256,
        )
        if self.definition.domain_id != self.EXPECTED_DOMAIN_ID:
            raise DomainContractError("adapter module and configuration disagree")

    def build_task(self, case_index: int) -> DomainTask:
        self._require_index(case_index)
        context = {
            field: f"{self.definition.domain_id}-{field}-{case_index % 17:02d}"
            for field in self.definition.task_fields
        }
        return DomainTask(
            schema_version="1.0",
            task_id=f"task_{canonical_hash({
                'domain': self.definition.domain_id,
                'case_index': case_index,
            })}",
            domain_id=self.definition.domain_id,
            objective=self.definition.task_objective,
            observable_context=context,
        )

    def build_candidate(
        self,
        task: DomainTask,
        case_index: int,
    ) -> DomainCandidate:
        self._require_index(case_index)
        parameters = {
            field: f"{field}-{case_index % 19:02d}"
            for field in self.definition.candidate_fields
        }
        return DomainCandidate(
            schema_version="1.0",
            candidate_id=f"candidate_{canonical_hash({
                'task_id': task.task_id,
                'action_type': self.definition.candidate_action_type,
                'parameters': parameters,
            })}",
            action_type=self.definition.candidate_action_type,
            parameters=parameters,
        )

    def instantiate_mechanism(
        self,
        mechanism: MechanismContract,
        case_index: int,
    ) -> DomainMechanism:
        self._require_index(case_index)
        facts: dict[str, Any] = {
            path: {
                "observed_state": f"state-{case_index % 5}",
                "evidence_id": f"evidence-{case_index % 23:02d}",
            }
            for path in mechanism.governance_paths
        }
        if mechanism.kind == "graph":
            facts["dependency_structure"] = {
                "nodes": [
                    {"id": f"node-{case_index % 7}-a"},
                    {"id": f"node-{case_index % 7}-b"},
                ],
                "edges": [
                    {
                        "source": f"node-{case_index % 7}-a",
                        "target": f"node-{case_index % 7}-b",
                        "edge_type": "registered_dependency",
                    }
                ],
            }
        elif mechanism.kind == "temporal":
            facts["temporal_state"] = {
                "event_index": case_index,
                "validity_window_id": f"window-{case_index % 11:02d}",
                "reversal_event_id": f"reversal-{case_index % 13:02d}",
            }
        elif mechanism.kind == "policy_grammar":
            facts["policy_expression"] = {
                "operator": "all",
                "terms": tuple(sorted(mechanism.governance_paths)),
                "version_id": f"grammar-{case_index % 5}",
            }
        elif mechanism.kind == "ambiguity":
            facts["resolution_channels"] = {
                "registered_query": "available" if case_index % 2 else "unavailable",
                "registered_view": "exhausted" if case_index % 3 else "unknown",
            }
        elif mechanism.kind == "composition":
            facts["composition_trace"] = {
                "term_count": len(mechanism.governance_paths),
                "composition_id": f"composition-{case_index % 29:02d}",
            }
        return DomainMechanism(
            schema_version="1.0",
            mechanism_id=mechanism.mechanism_id,
            kind=mechanism.kind,
            governing_facts=facts,
        )

    def project(
        self,
        task: DomainTask,
        candidate: DomainCandidate,
        mechanism: DomainMechanism,
        case_index: int,
    ) -> DomainProjection:
        predictive = {
            field: f"predictive-{field}-{case_index % 13:02d}"
            for field in self.definition.predictive_fields
        }
        raw = {
            field: {
                "state_id": f"{field}-{case_index % 7:02d}",
                "source": "registered_observation",
            }
            for field in self.definition.raw_governance_fields
        }
        raw["mechanism_observations"] = mechanism.governing_facts
        return DomainProjection(
            schema_version="1.0",
            task_projection={
                "task_id": task.task_id,
                "objective": task.objective,
                "observable_context": task.observable_context,
            },
            candidate_projection={
                "candidate_id": candidate.candidate_id,
                "action_type": candidate.action_type,
                "parameters": candidate.parameters,
            },
            predictive_projection=predictive,
            raw_governance_projection=raw,
        )

    def build_case(
        self,
        case_index: int,
        mechanism_index: int | None = None,
        label_swap_index: int | None = None,
        transform_index: int | None = None,
    ) -> DomainCase:
        self._require_index(case_index)
        mechanisms = self.definition.mechanisms
        mechanism = mechanisms[
            case_index % len(mechanisms)
            if mechanism_index is None
            else mechanism_index % len(mechanisms)
        ]
        swap = self.definition.label_swaps[
            case_index % len(self.definition.label_swaps)
            if label_swap_index is None
            else label_swap_index % len(self.definition.label_swaps)
        ]
        transform = self.definition.surface_transforms[
            case_index % len(self.definition.surface_transforms)
            if transform_index is None
            else transform_index % len(self.definition.surface_transforms)
        ]
        task = self.build_task(case_index)
        candidate = self.build_candidate(task, case_index)
        mechanism_instance = self.instantiate_mechanism(mechanism, case_index)
        projection = self.project(task, candidate, mechanism_instance, case_index)
        latent_meaning = {
            "task": task,
            "candidate": candidate,
            "mechanism": mechanism_instance,
            "projection": projection,
        }
        surface = self._surface(
            task,
            candidate,
            swap,
            transform,
            case_index,
        )
        case = DomainCase(
            schema_version="1.0",
            case_id=f"domain_case_{canonical_hash({
                'domain': self.definition.domain_id,
                'case_index': case_index,
                'mechanism': mechanism.mechanism_id,
                'swap': swap['swap_id'],
                'transform': transform['transform_id'],
            })}",
            domain_id=self.definition.domain_id,
            task=task,
            candidate=candidate,
            mechanism=mechanism_instance,
            projection=projection,
            surface=surface,
            label_swap_id=_text(swap.get("swap_id"), "swap_id"),
            surface_transform_id=_text(
                transform.get("transform_id"),
                "transform_id",
            ),
            latent_meaning_hash=canonical_hash(latent_meaning),
        )
        self.validate_case(case)
        return case

    def validate_case(self, case: DomainCase) -> None:
        if (
            case.domain_id != self.definition.domain_id
            or case.task.domain_id != self.definition.domain_id
        ):
            raise DomainContractError("case domain does not match adapter")
        if case.projection.schema_signature != universal_projection_signature():
            raise DomainContractError("case violates universal projection schema")
        serialized = str(
            {
                "surface": case.surface,
                "predictive": case.projection.predictive_projection,
                "raw": case.projection.raw_governance_projection,
            }
        ).lower()
        if any(token in serialized for token in TERMINAL_TOKENS):
            raise DomainContractError("case exposes a terminal label shortcut")
        if len(case.projection.raw_governance_projection) < 7:
            raise DomainContractError("case collapses Raw-G into a trivial feature")

    def anti_shortcut_variants(self, case_index: int) -> tuple[DomainCase, ...]:
        variants = [
            self.build_case(
                case_index,
                label_swap_index=swap_index,
                transform_index=transform_index,
            )
            for swap_index in range(len(self.definition.label_swaps))
            for transform_index in range(len(self.definition.surface_transforms))
        ]
        if (
            len({case.latent_meaning_hash for case in variants}) != 1
            or len({canonical_hash(case.projection) for case in variants}) != 1
            or len({case.surface_hash for case in variants}) != len(variants)
        ):
            raise DomainContractError(
                "anti-shortcut variants changed meaning/projection or collided"
            )
        return tuple(variants)

    def _surface(
        self,
        task: DomainTask,
        candidate: DomainCandidate,
        swap: Mapping[str, Any],
        transform: Mapping[str, Any],
        case_index: int,
    ) -> Mapping[str, Any]:
        aliases = _mapping(swap.get("aliases"), "swap aliases")
        style = _text(transform.get("operation"), "transform operation")
        fields: list[tuple[str, Any]] = [
            ("record_alias", aliases.get("record")),
            ("candidate_alias", aliases.get("candidate")),
            ("task_reference", task.task_id),
            ("candidate_reference", candidate.candidate_id),
            ("style", style),
            ("transform_nonce", f"surface-{case_index % 31:02d}"),
        ]
        if style == "reverse_order":
            fields.reverse()
        elif style == "identifier_remap":
            fields = [(f"field_{index:02d}", value) for index, (_, value) in enumerate(fields)]
        elif style == "distractor_insert":
            fields.append(("registered_distractor", f"neutral-{case_index % 37:02d}"))
        elif style != "compact_style":
            raise DomainContractError("unknown surface transform")
        return dict(fields)

    @staticmethod
    def _require_index(case_index: int) -> None:
        if not isinstance(case_index, int) or case_index < 0:
            raise DomainContractError("case_index must be a nonnegative integer")


def universal_projection_signature() -> tuple[tuple[str, str], ...]:
    return (
        ("task_projection", "mapping"),
        ("candidate_projection", "mapping"),
        ("predictive_projection", "mapping"),
        ("raw_governance_projection", "mapping"),
    )
