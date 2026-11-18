"""Prompt text for proposal generation. Business services call these builders."""

import json

from app.proposals.sections import PROMPT_VERSION, SECTION_SPECS

OUTLINE_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {
        "sections": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "key": {"type": "STRING"},
                    "title": {"type": "STRING"},
                    "objective": {"type": "STRING"},
                },
                "required": ["key", "title", "objective"],
            },
        }
    },
    "required": ["sections"],
}

SECTIONS_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {
        "sections": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "key": {"type": "STRING"},
                    "title": {"type": "STRING"},
                    "body": {"type": "STRING"},
                    "needs_review": {"type": "BOOLEAN"},
                    "review_notes": {"type": "STRING"},
                    "source_document_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["key", "title", "body", "needs_review", "review_notes", "source_document_ids"],
            },
        }
    },
    "required": ["sections"],
}

_RULES = """
Rules:
- Write a professional business proposal.
- Begin every section body with "AI draft."
- Treat the company profile and the retrieved document excerpts as the only verified facts.
- When a sentence uses a retrieved excerpt, name the source filename in the sentence.
- Never invent client achievements, company experience, case studies, certifications, staff, or references.
- Never invent prices, totals, rates, or payment amounts. Repeat a budget only when the input states it.
- When an input or verified fact is missing, say "Not provided — needs review." and set needs_review to true.
- Leave source_document_ids empty unless the section uses a retrieved excerpt. Use only the document ids listed below.
- Return JSON only.
""".strip()


def outline_prompt(context: dict[str, object]) -> str:
    keys = ", ".join(f"{key} ({title})" for key, title in SECTION_SPECS)
    return (
        f"Prompt version {PROMPT_VERSION}. Create an outline with exactly these sections, in this order: {keys}.\n"
        f"{_RULES}\n\nGeneration context:\n{json.dumps(context, indent=2)}"
    )


def sections_prompt(context: dict[str, object], outline: dict[str, object]) -> str:
    return (
        f"Prompt version {PROMPT_VERSION}. Write every section in the outline. "
        "Keep the same keys, titles, and order.\n"
        f"{_RULES}\n\nOutline:\n{json.dumps(outline, indent=2)}\n\nGeneration context:\n{json.dumps(context, indent=2)}"
    )
