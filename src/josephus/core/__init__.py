"""Core Josephus functionality."""

from josephus.core.config import Settings, get_settings

# Lazy imports to avoid circular import with analyzer
# Import these directly from josephus.core.service when needed


def __getattr__(name: str):
    """Lazy import to avoid circular imports."""
    if name in ("DocumentationResult", "JosephusService"):
        from josephus.core.service import DocumentationResult, JosephusService

        return {"DocumentationResult": DocumentationResult, "JosephusService": JosephusService}[
            name
        ]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DocumentationResult",
    "JosephusService",
    "Settings",
    "get_settings",
]
