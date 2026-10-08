"""Unit tests for artifact storage abstraction layer and Terraform configuration."""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.storage import (
    ArtifactStore,
    FakeArtifactStore,
    GCSArtifactStore,
    get_artifact_store,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INFRA_DIR = REPO_ROOT / "infra"


@pytest.mark.issue_25
def test_fake_artifact_store_crud() -> None:
    """Test FakeArtifactStore upload, download, exists, list_keys, and delete."""
    store: ArtifactStore = FakeArtifactStore(bucket_name="test-bucket")

    assert not store.exists("reports/summary.txt")
    assert store.list_keys() == []

    # Upload string
    uri1 = store.upload("reports/summary.txt", "Performance Summary Report", "text/plain")
    assert uri1 == "fake://test-bucket/reports/summary.txt"
    assert store.exists("reports/summary.txt")

    # Download string & bytes
    assert store.download_text("reports/summary.txt") == "Performance Summary Report"
    assert store.download("reports/summary.txt") == b"Performance Summary Report"

    # Upload bytes
    uri2 = store.upload("data/checkpoint.bin", b"\x00\x01\x02\x03")
    assert uri2 == "fake://test-bucket/data/checkpoint.bin"

    # List keys
    assert store.list_keys() == ["data/checkpoint.bin", "reports/summary.txt"]
    assert store.list_keys(prefix="reports/") == ["reports/summary.txt"]
    assert store.list_keys(prefix="nonexistent/") == []

    # Delete
    assert store.delete("reports/summary.txt") is True
    assert store.delete("reports/summary.txt") is False
    assert not store.exists("reports/summary.txt")
    assert store.list_keys() == ["data/checkpoint.bin"]


@pytest.mark.issue_25
def test_fake_artifact_store_file_not_found_errors() -> None:
    """Test that absent keys raise FileNotFoundError on download."""
    store = FakeArtifactStore()
    with pytest.raises(FileNotFoundError, match=r"Key 'missing\.json' not found"):
        store.download("missing.json")

    with pytest.raises(FileNotFoundError, match=r"Key 'missing\.json' not found"):
        store.download_text("missing.json")


@pytest.mark.issue_25
def test_fake_artifact_store_upload_file(tmp_path: Path) -> None:
    """Test uploading a local file from disk to FakeArtifactStore."""
    store = FakeArtifactStore()
    local_file = tmp_path / "model_weights.pt"
    local_file.write_bytes(b"binary-model-weights")

    uri = store.upload_file("models/v1.pt", local_file)
    assert uri == "fake://fake-artifacts-bucket/models/v1.pt"
    assert store.download("models/v1.pt") == b"binary-model-weights"

    # Missing local file
    missing_file = tmp_path / "nonexistent.pt"
    with pytest.raises(FileNotFoundError, match="Local file to upload not found"):
        store.upload_file("models/missing.pt", missing_file)


@pytest.mark.issue_25
def test_gcs_artifact_store_lazy_client_initialization() -> None:
    """Test GCSArtifactStore client and bucket property lazy initialization."""
    with patch("google.cloud.storage.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_cls.return_value = mock_client_instance

        store = GCSArtifactStore(bucket_name="my-bucket", project_id="my-project")
        assert store.bucket_name == "my-bucket"
        assert store.project_id == "my-project"

        # Access client property
        client = store.client
        assert client == mock_client_instance
        mock_client_cls.assert_called_once_with(project="my-project")

        # Access bucket property
        _ = store.bucket
        mock_client_instance.bucket.assert_called_once_with("my-bucket")


@pytest.mark.issue_25
def test_gcs_artifact_store_mocked_operations() -> None:
    """Test GCSArtifactStore CRUD operations with injected mock client."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    store = GCSArtifactStore(
        bucket_name="trading-bucket",
        project_id="test-proj",
        client=mock_client,
    )

    # Upload string
    uri_str = store.upload("logs/run.txt", "Execution log")
    assert uri_str == "gs://trading-bucket/logs/run.txt"
    mock_bucket.blob.assert_called_with("logs/run.txt")
    mock_blob.upload_from_string.assert_called_with(
        "Execution log", content_type="text/plain; charset=utf-8"
    )

    # Upload bytes with custom content-type
    uri_bytes = store.upload("data/out.csv", b"a,b\n1,2", content_type="text/csv")
    assert uri_bytes == "gs://trading-bucket/data/out.csv"
    mock_blob.upload_from_string.assert_called_with(b"a,b\n1,2", content_type="text/csv")

    # Exists
    mock_blob.exists.return_value = True
    assert store.exists("logs/run.txt") is True
    mock_blob.exists.return_value = False
    assert store.exists("logs/run.txt") is False

    # Download bytes & text success
    mock_blob.exists.return_value = True
    mock_blob.download_as_bytes.return_value = b"byte-content"
    assert store.download("data/out.csv") == b"byte-content"

    mock_blob.download_as_text.return_value = "text-content"
    assert store.download_text("logs/run.txt") == "text-content"

    # Download raises FileNotFoundError if blob does not exist
    mock_blob.exists.return_value = False
    with pytest.raises(FileNotFoundError, match=r"Blob 'logs/run\.txt' not found"):
        store.download("logs/run.txt")
    with pytest.raises(FileNotFoundError, match=r"Blob 'logs/run\.txt' not found"):
        store.download_text("logs/run.txt")

    # Delete
    mock_blob.exists.return_value = True
    assert store.delete("logs/run.txt") is True
    mock_blob.delete.assert_called_once()

    mock_blob.exists.return_value = False
    assert store.delete("logs/run.txt") is False

    # List keys
    mock_blob_1 = MagicMock()
    mock_blob_1.name = "reports/rep1.json"
    mock_blob_2 = MagicMock()
    mock_blob_2.name = "reports/rep2.json"
    mock_client.list_blobs.return_value = [mock_blob_1, mock_blob_2]

    keys = store.list_keys(prefix="reports/")
    assert keys == ["reports/rep1.json", "reports/rep2.json"]
    mock_client.list_blobs.assert_called_with(mock_bucket, prefix="reports/")


@pytest.mark.issue_25
def test_gcs_artifact_store_upload_file(tmp_path: Path) -> None:
    """Test GCSArtifactStore upload_file with mock client."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    store = GCSArtifactStore(
        bucket_name="trading-bucket",
        client=mock_client,
    )

    local_path = tmp_path / "chart.png"
    local_path.write_bytes(b"\x89PNG")

    uri = store.upload_file("charts/chart.png", local_path, content_type="image/png")
    assert uri == "gs://trading-bucket/charts/chart.png"
    mock_blob.upload_from_filename.assert_called_once_with(
        str(local_path), content_type="image/png"
    )

    missing = tmp_path / "nonexistent.png"
    with pytest.raises(FileNotFoundError, match="Local file to upload not found"):
        store.upload_file("charts/missing.png", missing)


@pytest.mark.issue_25
def test_get_artifact_store_factory() -> None:
    """Test get_artifact_store factory function returns correct instance."""
    # When gcs_artifacts_bucket is empty or None -> FakeArtifactStore
    settings_fake = Settings(gcs_artifacts_bucket="")
    store1 = get_artifact_store(settings_fake)
    assert isinstance(store1, FakeArtifactStore)

    # When gcs_artifacts_bucket is set -> GCSArtifactStore
    settings_gcs = Settings(
        gcs_artifacts_bucket="prod-trading-artifacts",
        gcp_project_id="trading-project-123",
    )
    store2 = get_artifact_store(settings_gcs)
    assert isinstance(store2, GCSArtifactStore)
    assert store2.bucket_name == "prod-trading-artifacts"
    assert store2.project_id == "trading-project-123"


@pytest.mark.issue_25
def test_terraform_files_exist_and_contain_expected_specifications() -> None:
    """Validate Terraform configuration files in infra/."""
    assert (INFRA_DIR / "main.tf").is_file()
    assert (INFRA_DIR / "variables.tf").is_file()
    assert (INFRA_DIR / "outputs.tf").is_file()
    assert (INFRA_DIR / "terraform.tfvars.example").is_file()

    main_tf = (INFRA_DIR / "main.tf").read_text(encoding="utf-8")
    assert 'resource "google_storage_bucket" "artifacts"' in main_tf
    assert "uniform_bucket_level_access = true" in main_tf
    assert "versioning" in main_tf
    assert "lifecycle_rule" in main_tf

    variables_tf = (INFRA_DIR / "variables.tf").read_text(encoding="utf-8")
    assert 'variable "project_id"' in variables_tf
    assert 'variable "region"' in variables_tf
    assert 'variable "bucket_name"' in variables_tf

    outputs_tf = (INFRA_DIR / "outputs.tf").read_text(encoding="utf-8")
    assert 'output "bucket_name"' in outputs_tf
    assert 'output "bucket_url"' in outputs_tf
    assert 'output "bucket_self_link"' in outputs_tf


@pytest.mark.issue_25
def test_terraform_formatting() -> None:
    """Run terraform fmt -check infra/ if terraform CLI binary is installed."""
    terraform_bin = shutil.which("terraform")
    if not terraform_bin:
        pytest.skip("terraform CLI is not installed in environment")

    result = subprocess.run(  # noqa: S603
        [terraform_bin, "fmt", "-check", str(INFRA_DIR)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"terraform fmt -check failed:\n{result.stderr}\n{result.stdout}"
