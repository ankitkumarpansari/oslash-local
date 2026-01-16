"""Connectors module for OSlash Local."""

from oslash.connectors.base import BaseConnector, SyncResult, FileInfo
from oslash.connectors.gdrive import GoogleDriveConnector, create_gdrive_connector
from oslash.connectors.gmail import GmailConnector, create_gmail_connector
from oslash.connectors.slack import SlackConnector, create_slack_connector

__all__ = [
    "BaseConnector",
    "SyncResult",
    "FileInfo",
    "GoogleDriveConnector",
    "create_gdrive_connector",
    "GmailConnector",
    "create_gmail_connector",
    "SlackConnector",
    "create_slack_connector",
]
