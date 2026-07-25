from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import os


class CredentialError(RuntimeError):
    pass


@dataclass
class EnvironmentCredentialProvider:
    """
    Secrets are referenced, never stored directly in the research database.

    Example:
        secret_reference = "env:BENZINGA_API_KEY"
    """

    def resolve(self, secret_reference: str) -> str:
        prefix, _, key = secret_reference.partition(":")
        if prefix != "env" or not key:
            raise CredentialError("Only env:<VARIABLE> references are supported.")
        value = os.getenv(key)
        if not value:
            raise CredentialError(f"Environment variable {key} is not set.")
        return value
