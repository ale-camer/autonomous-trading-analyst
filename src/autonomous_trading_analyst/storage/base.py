"""Abstract interface definition for artifact storage."""

from abc import ABC, abstractmethod
from pathlib import Path


class ArtifactStore(ABC):
    """Abstract interface for storing and retrieving trading artifacts and reports."""

    @abstractmethod
    def upload(
        self,
        key: str,
        data: bytes | str,
        content_type: str | None = None,
    ) -> str:
        """Upload raw binary or text data under the specified key and return its URI."""

    @abstractmethod
    def download(self, key: str) -> bytes:
        """Download raw binary content for the given key.

        Raises:
            FileNotFoundError: If the specified key does not exist.
        """

    def download_text(self, key: str, encoding: str = "utf-8") -> str:
        """Download text content for the given key.

        Raises:
            FileNotFoundError: If the specified key does not exist.
        """
        raw_bytes = self.download(key)
        return raw_bytes.decode(encoding)

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check whether an artifact exists under the specified key."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete the artifact at the specified key.

        Returns:
            True if the artifact was found and deleted, False otherwise.
        """

    @abstractmethod
    def list_keys(self, prefix: str = "") -> list[str]:
        """List all artifact keys matching the specified prefix."""

    def upload_file(
        self,
        key: str,
        file_path: str | Path,
        content_type: str | None = None,
    ) -> str:
        """Upload a local file to the artifact store and return its URI."""
        path = Path(file_path)
        if not path.exists():
            msg = f"Local file to upload not found: {path}"
            raise FileNotFoundError(msg)
        data = path.read_bytes()
        return self.upload(key=key, data=data, content_type=content_type)
