"""The sections every generated proposal contains, in display order."""

SECTION_SPECS: tuple[tuple[str, str], ...] = (
    ("executive_summary", "Executive Summary"),
    ("client_requirements", "Client Requirements"),
    ("proposed_solution", "Proposed Solution"),
    ("scope_of_work", "Scope of Work"),
    ("deliverables", "Deliverables"),
    ("implementation_methodology", "Implementation Methodology"),
    ("project_timeline", "Project Timeline"),
    ("budget_and_cost", "Budget and Cost Breakdown"),
    ("terms_and_conditions", "Terms and Conditions"),
    ("conclusion", "Conclusion"),
)

SECTION_KEYS = tuple(key for key, _title in SECTION_SPECS)
PROMPT_VERSION = "proposal-v1"
