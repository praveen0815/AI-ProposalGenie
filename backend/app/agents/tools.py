"""Controlled tools. Agents cannot pass a company id, SQL, or a shell command."""

import json
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.agents.errors import AgentOutputError
from app.integrations.llm.prompts import SECTIONS_SCHEMA
from app.integrations.llm.provider import StructuredLanguageModel
from app.proposals.sections import SECTION_KEYS, SECTION_SPECS

_TITLES = dict(SECTION_SPECS)


class KnowledgeQuery(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class KnowledgeChunk(BaseModel):
    document_id: str
    filename: str
    chunk_index: int
    excerpt: str
    score: float


class KnowledgeResult(BaseModel):
    status: str
    chunks: list[KnowledgeChunk]


class ClientResult(BaseModel):
    name: str
    industry: str | None = None
    website: str | None = None


class ResearchQuery(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class ExternalHit(BaseModel):
    title: str = Field(max_length=300)
    url: str = Field(max_length=500)
    snippet: str = Field(max_length=1000)


class ExternalResearchResult(BaseModel):
    status: str
    results: list[ExternalHit]


class SectionDraft(BaseModel):
    key: str
    title: str
    body: str = Field(min_length=1)
    needs_review: bool = False
    review_notes: str = ""
    source_document_ids: list[str] = Field(default_factory=list)


class SectionDocument(BaseModel):
    sections: list[SectionDraft]


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str]


class AgentTools(Protocol):
    def company_knowledge(self, query: str) -> KnowledgeResult:
        """Retrieve chunks for the company already bound to this workflow."""

    def client_info(self) -> ClientResult:
        """Read the client stored on the proposal."""

    def external_research(self, query: str) -> ExternalResearchResult:
        """Call the configured research source, or report that none is configured."""

    def generate_sections(self, *, prompt: str, allowed_document_ids: set[str]) -> list[dict[str, Any]]:
        """Generate proposal sections and reject ids that were not retrieved."""

    def validate_sections(self, sections: list[dict[str, Any]]) -> ValidationResult:
        """Check the required section structure."""


def parse_json_object(text: str, node: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AgentOutputError("The agent returned a result that could not be validated", node) from exc
    if not isinstance(parsed, dict):
        raise AgentOutputError("The agent returned a result that could not be validated", node)
    return parsed


def validate_model(model: type[BaseModel], payload: dict[str, Any], node: str) -> BaseModel:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise AgentOutputError("The agent returned a result that could not be validated", node) from exc


class WorkflowTools:
    """Tool implementations whose company scope is fixed by the workflow runner."""

    def __init__(
        self,
        *,
        company_id: str,
        client: ClientResult,
        model: StructuredLanguageModel,
        retrieve_knowledge,
        research_api_key: str,
        research_base_url: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._company_id = company_id
        self._client = client
        self._model = model
        self._retrieve = retrieve_knowledge
        self._research_api_key = research_api_key
        self._research_base_url = research_base_url
        self._transport = transport

    def company_knowledge(self, query: str) -> KnowledgeResult:
        checked = KnowledgeQuery(query=query.strip())
        if not self._company_id:
            return KnowledgeResult(status="unavailable", chunks=[])
        try:
            chunks = self._retrieve(checked.query)
        except Exception:
            return KnowledgeResult(status="unavailable", chunks=[])
        parsed = [
            KnowledgeChunk(
                document_id=str(chunk.document_id),
                filename=chunk.filename,
                chunk_index=chunk.chunk_index,
                excerpt=chunk.text[:1200],
                score=chunk.score,
            )
            for chunk in chunks
        ]
        return KnowledgeResult(status="available" if parsed else "empty", chunks=parsed)

    def client_info(self) -> ClientResult:
        return self._client

    def external_research(self, query: str) -> ExternalResearchResult:
        ResearchQuery(query=query.strip())
        if not self._research_api_key.strip() or not self._research_base_url.strip():
            return ExternalResearchResult(status="not_configured", results=[])
        try:
            with httpx.Client(timeout=20, transport=self._transport) as client:
                response = client.post(
                    self._research_base_url,
                    headers={"Authorization": f"Bearer {self._research_api_key}"},
                    json={"query": query.strip()},
                )
            response.raise_for_status()
            body = response.json()
        except Exception:
            return ExternalResearchResult(status="failed", results=[])
        results = []
        for item in body.get("results", []) if isinstance(body, dict) else []:
            try:
                results.append(ExternalHit.model_validate(item))
            except ValidationError:
                continue
        return ExternalResearchResult(status="completed", results=results[:5])

    def generate_sections(self, *, prompt: str, allowed_document_ids: set[str]) -> list[dict[str, Any]]:
        completion = self._model.generate_json(purpose="agent_sections", prompt=prompt, schema=SECTIONS_SCHEMA)
        document = validate_model(SectionDocument, parse_json_object(completion.text, "proposal_writer"), "proposal_writer")
        keys = tuple(section.key for section in document.sections)
        if keys != SECTION_KEYS:
            raise AgentOutputError("The agent returned a result that could not be validated", "proposal_writer")
        normalized: list[dict[str, Any]] = []
        for section in document.sections:
            body = section.body.strip()
            if not body.lower().startswith("ai draft"):
                body = f"AI draft.\n\n{body}"
            source_ids = [document_id for document_id in section.source_document_ids if document_id in allowed_document_ids]
            normalized.append(
                {
                    "key": section.key,
                    "title": _TITLES[section.key],
                    "body": body,
                    "needs_review": section.needs_review,
                    "review_notes": section.review_notes.strip(),
                    "source_document_ids": source_ids,
                }
            )
        return normalized

    def validate_sections(self, sections: list[dict[str, Any]]) -> ValidationResult:
        errors: list[str] = []
        keys = [section.get("key") for section in sections if isinstance(section, dict)]
        if tuple(keys) != SECTION_KEYS:
            errors.append("The proposal is missing a required section.")
        for section in sections:
            if not isinstance(section, dict):
                errors.append("A section was not an object.")
                continue
            body = str(section.get("body") or "").strip()
            if not body:
                errors.append(f"{section.get('title', 'A section')} is empty.")
            elif not body.lower().startswith("ai draft"):
                errors.append(f"{section.get('title', 'A section')} is not marked as an AI draft.")
        return ValidationResult(valid=not errors, errors=errors)
