"""Data models for structured output and signal extraction."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SignalType(str, Enum):
    """Types of business signals that can be extracted."""

    EXPANSION = "expansion"
    HIRING = "hiring"
    SUSTAINABILITY = "sustainability"
    CAPEX_INVESTMENT = "capex_investment"
    SUPPLY_CHAIN = "supply_chain"
    DIGITAL_TRANSFORMATION = "digital_transformation"
    COMPETITOR_ACTIVITY = "competitor_activity"
    PARTNERSHIP = "partnership"
    PROCUREMENT = "procurement"
    ESG_INITIATIVE = "esg_initiative"


class SourceType(str, Enum):
    """Source of the extracted signal."""

    WEBSITE = "website"
    ANNUAL_REPORT = "annual_report"
    ESG_REPORT = "esg_report"
    LINKEDIN = "linkedin"
    NEWS = "news"
    PDF = "pdf"


class ConfidenceLevel(str, Enum):
    """Confidence level of the extracted signal."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class BusinessSignal:
    """Structured business signal extracted from content."""

    account_id: str
    signal_type: SignalType
    description: str
    confidence_score: float  # 0.0 to 1.0
    confidence_level: ConfidenceLevel
    source_type: SourceType
    source_url: Optional[str] = None
    raw_snippet: Optional[str] = None
    entity_names: List[str] = field(default_factory=list)
    key_metrics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    method: str = "rule_engine"  # rule_engine or llm_verified
    llm_reason: Optional[str] = None
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        data["signal_type"] = self.signal_type.value
        data["source_type"] = self.source_type.value
        data["confidence_level"] = self.confidence_level.value
        data["extracted_at"] = self.extracted_at.isoformat()
        return data

    def to_json_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return self.to_dict()


class SignalExtractionRequest(BaseModel):
    """Request to extract signals from text."""

    account_id: str
    company_name: str
    text: str
    source_type: SourceType
    source_url: Optional[str] = None
    signal_types: List[SignalType] = Field(
        default_factory=lambda: [st for st in SignalType]
    )


class SignalExtractionResponse(BaseModel):
    """Response from signal extraction."""

    account_id: str
    company_name: str
    signals_count: int
    confidence_avg: float
    signals: List[dict]
    processing_time_ms: float
    status: str = "success"


class ScraperResult(BaseModel):
    """Result from a scraper operation."""

    source: str  # news, annual_report, hiring, esg, website
    account_id: str
    company_name: str
    content: str
    url: Optional[str] = None
    status: str  # success, error, empty, timeout
    error_message: Optional[str] = None
    extraction_time_ms: float
    content_length: int


class VerificationResult(BaseModel):
    """Result from signal verification."""

    signal_id: str
    is_valid: bool
    confidence_adjustment: float  # -0.5 to +0.5
    verification_reason: str
    verified_at: datetime = Field(default_factory=datetime.utcnow)


class PipelineStats(BaseModel):
    """Statistics for the entire pipeline run."""

    total_signals_extracted: int = 0
    high_confidence_signals: int = 0
    medium_confidence_signals: int = 0
    low_confidence_signals: int = 0
    average_confidence: float = 0.0
    sources_used: List[SourceType] = Field(default_factory=list)
    signal_types_found: List[SignalType] = Field(default_factory=list)
    total_processing_time_ms: float = 0.0
    errors_encountered: int = 0
    warnings: List[str] = Field(default_factory=list)
