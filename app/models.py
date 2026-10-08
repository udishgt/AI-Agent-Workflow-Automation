"""Data models used by the workflow loader."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Workflow:
    """A workflow row loaded from the Excel workbook."""

    workflow_id: Any
    workflow_name: Any
    fields: dict[str, Any]

    @property
    def id(self) -> Any:
        """Return the workflow identifier."""
        return self.workflow_id

    @property
    def name(self) -> Any:
        """Return the workflow name."""
        return self.workflow_name

    def __getitem__(self, column: str) -> Any:
        """Return a value by its Excel column name."""
        return self.fields[column]


@dataclass(frozen=True)
class WorkflowSelection:
    """The workflow selected for a user request."""

    workflow_id: Any
    reason: str
    confidence: float


@dataclass
class ExecutionContext:
    """Mutable state shared by all steps in one execution."""

    request: str
    state: dict[str, Any]


@dataclass(frozen=True)
class StepHandlerResult:
    """Provider-neutral output returned by an injected step handler."""

    result: Any = None
    tool_used: str | None = None
    decisions: list[Any] = field(default_factory=list)


@dataclass(frozen=True)
class StepResult:
    """Trace entry for one workflow step."""

    name: str
    status: str
    tool_used: str | None = None
    result: Any = None
    error: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """Structured result of a generic workflow execution."""

    workflow_id: Any
    workflow_name: Any
    status: str
    steps_executed: list[StepResult]
    tools_used: list[str]
    decisions: list[Any]
    final_output: Any
    errors: list[str]


@dataclass(frozen=True)
class StepDefinition:
    """A parsed step description from a workflow's Excel row."""

    name: str


@dataclass(frozen=True)
class PlannedStep:
    """A resolver decision connecting one workflow step to a registered tool."""

    step: StepDefinition
    tool_name: str | None
    arguments: dict[str, Any]
    error: str | None = None


@dataclass(frozen=True)
class AgentResult:
    """Complete public result returned by the agent orchestrator."""

    request: str
    workflow_id: Any = None
    workflow_name: Any = None
    selection_reason: str | None = None
    confidence: float | None = None
    execution: ExecutionResult | None = None
    status: str = "failed"
    errors: list[str] = field(default_factory=list)
