"""Connectors module for OSlash Local."""

from oslash.connectors.base import BaseConnector, SyncResult
from oslash.connectors.gdrive import GoogleDriveConnector

__all__ = [
    "BaseConnector",
    "SyncResult",
    "GoogleDriveConnector",
]
