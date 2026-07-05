"""Optional compatibility shims for model/provider quirks."""

from pika.compat.gemini import install as install_gemini_compat

__all__ = ["install_gemini_compat"]
