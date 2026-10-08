"""Google Cloud Storage implementation of ArtifactStore."""

from pathlib import Path
from typing import cast

from google.cloud import storage

from autonomous_trading_analyst.storage.base import ArtifactStore


class GCSArtifactStore(ArtifactStore):
    """Google Cloud Storage backed artifact store for production cloud archiving."""

    def __init__(
        self,
        bucket_name: str,
        project_id: str | None = None,
        client: storage.Client | None = None,
    ) -> None:
        self.bucket_name = bucket_name
        self.project_id = project_id
        self._client = client

    @property
    def client(self) -> storage.Client:
        """Lazily initialize or return the injected GCS storage Client."""
        if self._client is None:
            self._client = storage.Client(project=self.project_id)
        return self._client

    @property
    def bucket(self) -> storage.Bucket:
        """Return the target GCS Bucket instance."""
        return self.client.bucket(self.bucket_name)

    def upload(
        self,
        key: str,
        data: bytes | str,
        content_type: str | None = None,
    ) -> str:
        """Upload raw data to a GCS blob and return the gs:// URI."""
        blob = self.bucket.blob(key)
        if isinstance(data, str):
            c_type = content_type or "text/plain; charset=utf-8"
            blob.upload_from_string(data, content_type=c_type)
        else:
            c_type = content_type or "application/octet-stream"
            blob.upload_from_string(data, content_type=c_type)
        return f"gs://{self.bucket_name}/{key}"

    def download(self, key: str) -> bytes:
        """Download raw binary bytes from a GCS blob.

        Raises:
            FileNotFoundError: If the blob does not exist in the bucket.
        """
        blob = self.bucket.blob(key)
        if not blob.exists():
            msg = f"Blob '{key}' not found in bucket '{self.bucket_name}'"
            raise FileNotFoundError(msg)
        return cast(bytes, blob.download_as_bytes())

    def download_text(self, key: str, encoding: str = "utf-8") -> str:
        """Download text content from a GCS blob.

        Raises:
            FileNotFoundError: If the blob does not exist in the bucket.
        """
        blob = self.bucket.blob(key)
        if not blob.exists():
            msg = f"Blob '{key}' not found in bucket '{self.bucket_name}'"
            raise FileNotFoundError(msg)
        return cast(str, blob.download_as_text(encoding=encoding))

    def exists(self, key: str) -> bool:
        """Check whether a GCS blob exists."""
        blob = self.bucket.blob(key)
        return bool(blob.exists())

    def delete(self, key: str) -> bool:
        """Delete a GCS blob if present.

        Returns:
            True if the blob was found and deleted, False otherwise.
        """
        blob = self.bucket.blob(key)
        if not blob.exists():
            return False
        blob.delete()
        return True

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all blob keys in the bucket matching the given prefix."""
        blobs = self.client.list_blobs(self.bucket, prefix=prefix or None)
        return [b.name for b in blobs]

    def upload_file(
        self,
        key: str,
        file_path: str | Path,
        content_type: str | None = None,
    ) -> str:
        """Upload a local file directly to a GCS blob."""
        path = Path(file_path)
        if not path.exists():
            msg = f"Local file to upload not found: {path}"
            raise FileNotFoundError(msg)

        blob = self.bucket.blob(key)
        blob.upload_from_filename(str(path), content_type=content_type)
        return f"gs://{self.bucket_name}/{key}"
