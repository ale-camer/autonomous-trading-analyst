"""Artifact storage interfaces and cloud implementations."""

from autonomous_trading_analyst.storage.base import ArtifactStore
from autonomous_trading_analyst.storage.factory import get_artifact_store
from autonomous_trading_analyst.storage.fake import FakeArtifactStore
from autonomous_trading_analyst.storage.gcs import GCSArtifactStore

__all__ = [
    "ArtifactStore",
    "FakeArtifactStore",
    "GCSArtifactStore",
    "get_artifact_store",
]
