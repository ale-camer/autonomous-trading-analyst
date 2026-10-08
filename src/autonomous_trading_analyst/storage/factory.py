"""Factory function resolving configured ArtifactStore implementation."""

from autonomous_trading_analyst.config import Settings, get_settings
from autonomous_trading_analyst.storage.base import ArtifactStore
from autonomous_trading_analyst.storage.fake import FakeArtifactStore
from autonomous_trading_analyst.storage.gcs import GCSArtifactStore


def get_artifact_store(settings: Settings | None = None) -> ArtifactStore:
    """Return configured GCSArtifactStore if bucket configured, else FakeArtifactStore."""
    cfg = settings if settings is not None else get_settings()

    if cfg.gcs_artifacts_bucket:
        return GCSArtifactStore(
            bucket_name=cfg.gcs_artifacts_bucket,
            project_id=cfg.gcp_project_id,
        )

    return FakeArtifactStore()
