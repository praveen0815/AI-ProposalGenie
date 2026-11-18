"""Errors raised by a language-model provider. Messages stay safe to log."""


class LLMError(Exception):
    """The provider could not complete a generation request."""


class LLMTimeout(LLMError):
    """The provider did not respond before the timeout, including retries."""


class LLMAPIError(LLMError):
    """The provider returned an error after the bounded retries."""


class LLMResponseError(LLMError):
    """The provider response was empty or was not the requested JSON."""
