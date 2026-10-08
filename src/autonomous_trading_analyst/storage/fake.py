"""In-memory fake implementation of ArtifactStore for deterministic offline testing."""

from autonomous_trading_analyst.storage.base import ArtifactStore


class FakeArtifactStore(ArtifactStore):
    """In-memory dictionary-backed artifact store for local offline testing."""

    def __init__(self, bucket_name: str = "fake-artifacts-bucket") -> None:
        self.bucket_name = bucket_name
        self._store: dict[str, tuple[bytes, str | None]] = {}

    def upload(
        self,
        key: str,
        data: bytes | str,
        content_type: str | None = None,
    ) -> str:
        """Store raw binary or string data in memory and return a fake URI."""
        raw_bytes = data.encode("utf-8") if isinstance(data, str) else data
        self._store[key] = (raw_bytes, content_type)
        return f"fake://{self.bucket_name}/{key}"

    def download(self, key: str) -> bytes:
        """Retrieve binary content from memory, raising FileNotFoundError if absent."""
        if key not in self._store:
            msg = f"Key '{key}' not found in FakeArtifactStore"
            raise FileNotFoundError(msg)
        return self._store[key][0]

    def exists(self, key: str) -> bool:
        """Check if key exists in the in-memory store."""
        return key in self._store

    def delete(self, key: str) -> bool:
        """Delete key from the in-memory store."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def list_keys(self, prefix: str = "") -> list[str]:
        """Return all keys matching the given prefix, sorted alphabetically."""
        return sorted([k for k in self._store if k.startswith(prefix)])
