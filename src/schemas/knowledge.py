"""
Pydantic v2 models for Structured Knowledge Base used in a RAG platform.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# BASE MODEL
# =============================================================================


class StrictBaseModel(BaseModel):
    """Reusable strict base model that forbids extra fields."""

    model_config = ConfigDict(extra="forbid")


# =============================================================================
# ENUM TYPES
# =============================================================================


KnowledgeType = Literal[
    "root_cause_analysis",
    "cli_command_reference",
    "escalation_resolution",
    "configuration_parameter",
]

SeverityLevel = Literal["S1", "S2", "S3", "S4"]


# =============================================================================
# SUPPORTING MODEL
# =============================================================================


class Source(StrictBaseModel):
    """Source model for tracking document origins."""

    doc_id: str
    filename: str
    page_number: int | None = None
    section_path: str | None = None
    chunk_id: str | None = None

    @field_validator("page_number")
    @classmethod
    def validate_page_number(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("page_number must be >= 1 if present")
        return v


# =============================================================================
# NESTED STRUCTURE MODELS
# =============================================================================


class RootCauseDetail(StrictBaseModel):
    """Root cause detail information."""

    summary: str
    affected_versions: list[str] = Field(default_factory=list)
    fixed_in: list[str] = Field(default_factory=list)


class FixDetail(StrictBaseModel):
    """Fix detail information."""

    steps: list[str] = Field(default_factory=list)
    cli_commands: list[str] = Field(default_factory=list)
    config_params: list[str] = Field(default_factory=list)
    estimated_time_minutes: int | None = None

    @field_validator("estimated_time_minutes")
    @classmethod
    def validate_estimated_time(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("estimated_time_minutes must be >= 0 if present")
        return v


class CommandParameter(StrictBaseModel):
    """Command parameter information."""

    name: str
    required: bool
    description: str


class CommandExample(StrictBaseModel):
    """Command example with usage and output."""

    usage: str
    output: str | None = None


class TimelineEvent(StrictBaseModel):
    """Timeline event for escalation tracking."""

    timestamp: datetime
    action: str
    by: str


class ResolutionDetail(StrictBaseModel):
    """Resolution detail information."""

    summary: str
    steps_taken: list[str] = Field(default_factory=list)
    prevention: list[str] = Field(default_factory=list)


class VersionInfo(StrictBaseModel):
    """Version information for configuration parameters."""

    introduced: str | None = None
    deprecated: str | None = None


# =============================================================================
# STRUCTURED KNOWLEDGE MODELS
# =============================================================================


class RootCauseAnalysis(StrictBaseModel):
    """Root cause analysis knowledge object."""

    title: str
    symptoms: list[str] = Field(default_factory=list)
    severity: SeverityLevel
    root_cause: RootCauseDetail
    fix: FixDetail


class CLICommandReference(StrictBaseModel):
    """CLI command reference knowledge object."""

    command: str
    syntax: str
    parameters: list[CommandParameter] = Field(default_factory=list)
    examples: list[CommandExample] = Field(default_factory=list)
    related_commands: list[str] = Field(default_factory=list)
    min_version: str | None = None


class EscalationResolution(StrictBaseModel):
    """Escalation resolution knowledge object."""

    escalation_id: str
    customer_impact: str
    severity: SeverityLevel
    timeline: list[TimelineEvent] = Field(default_factory=list)
    resolution: ResolutionDetail
    linked_defects: list[str] = Field(default_factory=list)


class ConfigurationParameter(StrictBaseModel):
    """Configuration parameter knowledge object."""

    param: str
    scope: str
    value_type: str
    default: str | int | float | bool | None = None
    recommended: str | int | float | bool | None = None
    unit: str | None = None
    description: str
    side_effects: list[str] = Field(default_factory=list)
    versions: VersionInfo


# =============================================================================
# DISCRIMINATED UNION TYPE FOR TYPE SAFETY
# =============================================================================


KnowledgeData = (
    RootCauseAnalysis | CLICommandReference | EscalationResolution | ConfigurationParameter
)


# =============================================================================
# MAIN ENVELOPE MODEL
# =============================================================================


class KnowledgeObject(StrictBaseModel):
    """
    Main wrapper model for knowledge base entries.
    The type field determines which model should be in the data field.
    """

    id: str
    type: KnowledgeType
    version: int = 1
    sources: list[Source] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    created_by: str
    chunk_hash: str
    tags: list[str] = Field(default_factory=list)
    data: KnowledgeData

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: int) -> int:
        if v < 1:
            raise ValueError("version must be >= 1")
        return v
