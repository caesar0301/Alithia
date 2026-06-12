"""PaperScout email utilities under plugins namespace.

Compatibility shim forwarding to canonical implementation.
"""

from alithia_agent.paperscout import email as _legacy_email


def __getattr__(name: str):
    return getattr(_legacy_email, name)


def __dir__():
    return sorted(set(globals().keys()) | set(dir(_legacy_email)))

