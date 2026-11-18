"""Domain enumerations stored as constrained strings."""

import enum


class MembershipRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class ProposalStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    SENT = "SENT"
    ARCHIVED = "ARCHIVED"


class DocumentFileType(str, enum.Enum):
    PDF = "PDF"
    DOCX = "DOCX"
    TXT = "TXT"
    MARKDOWN = "MARKDOWN"


class DocumentProcessingStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IndexStatus(str, enum.Enum):
    NOT_INDEXED = "NOT_INDEXED"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class AgentRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
