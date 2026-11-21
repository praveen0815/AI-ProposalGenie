"""Mark user and document text so a model treats it as data."""

import json


def fence(source: str, value: object) -> str:
    """Wrap untrusted text. The source label is chosen by the application."""

    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, default=str)
    safe = text.replace("</untrusted>", "< /untrusted>")
    return f'<untrusted source="{source}">\n{safe}\n</untrusted>'
