# Issue 25: GCS Artifact Store & Terraform

**Branch**: `feature/issue-25-gcs-terraform`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #25)
**Milestone**: M5 - Platform & Delivery (Closes M5)

## Objective
Implement the `ArtifactStore` abstraction layer in `src/autonomous_trading_analyst/storage/` supporting both an in-memory/local `FakeArtifactStore` and a cloud-backed `GCSArtifactStore` for persisting backtest reports, equity curves, and reasoning trace exports. Implement Infrastructure as Code (IaC) with Terraform in `infra/` to provision the Google Cloud Storage bucket with uniform bucket-level access control, object versioning, and lifecycle management policies.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/storage/base.py` defines the abstract `ArtifactStore` interface providing `upload`, `download`, `download_text`, `exists`, `delete`, `list_keys`, and `upload_file`.
- [x] `src/autonomous_trading_analyst/storage/fake.py` implements `FakeArtifactStore` maintaining in-memory storage for deterministic, fast offline testing.
- [x] `src/autonomous_trading_analyst/storage/gcs.py` implements `GCSArtifactStore` wrapping `google-cloud-storage` for production artifact archiving.
- [x] `src/autonomous_trading_analyst/storage/factory.py` implements `get_artifact_store` selecting `GCSArtifactStore` when configured or defaulting to `FakeArtifactStore`.
- [x] `src/autonomous_trading_analyst/storage/__init__.py` re-exports storage classes and factory.
- [x] `infra/main.tf`, `infra/variables.tf`, `infra/outputs.tf`, and `infra/terraform.tfvars.example` define Terraform configuration provisioning the GCS bucket with uniform bucket-level access, object versioning, and lifecycle rules.
- [x] `pyproject.toml` registers the `issue_25: GCS artifact store & Terraform` pytest marker.
- [x] `tests/unit/test_storage.py` validates `FakeArtifactStore`, `GCSArtifactStore` (with mocked GCS client), factory resolution, and Terraform syntax and structure (marked `@pytest.mark.issue_25`).
- [x] `make check` and `make test-issue ID=25` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=25 NAME=gcs-terraform
```

### 2. ArtifactStore Base Interface
- **File**: `src/autonomous_trading_analyst/storage/base.py`
- **Change**: Define `ArtifactStore` ABC:
  - `upload(key: str, data: bytes | str, content_type: str | None = None) -> str`
  - `download(key: str) -> bytes`
  - `download_text(key: str, encoding: str = "utf-8") -> str`
  - `exists(key: str) -> bool`
  - `delete(key: str) -> bool`
  - `list_keys(prefix: str = "") -> list[str]`
  - `upload_file(key: str, file_path: str | Path, content_type: str | None = None) -> str`

### 3. Fake Artifact Store
- **File**: `src/autonomous_trading_analyst/storage/fake.py`
- **Change**: Implement `FakeArtifactStore(ArtifactStore)`:
  - In-memory dictionary `_store: dict[str, tuple[bytes, str | None]]`.
  - Deterministic URI format `fake://{bucket_name}/{key}`.
  - Implements full CRUD, existence checks, prefix listing, and file upload.

### 4. Google Cloud Storage Artifact Store
- **File**: `src/autonomous_trading_analyst/storage/gcs.py`
- **Change**: Implement `GCSArtifactStore(ArtifactStore)`:
  - Takes `bucket_name: str`, `project_id: str | None = None`, `client: storage.Client | None = None`.
  - Interacts with Google Cloud Storage blobs.
  - URI format `gs://{bucket_name}/{key}`.
  - Sets `content_type` on blob upload, raises `FileNotFoundError` on missing keys during download.

### 5. Storage Factory & Package Exports
- **File**: `src/autonomous_trading_analyst/storage/factory.py`
  - `get_artifact_store(settings: Settings | None = None) -> ArtifactStore`: returns `GCSArtifactStore` if `settings.gcs_artifacts_bucket` is specified; otherwise returns `FakeArtifactStore`.
- **File**: `src/autonomous_trading_analyst/storage/__init__.py`
  - Re-exports `ArtifactStore`, `FakeArtifactStore`, `GCSArtifactStore`, and `get_artifact_store`.

### 6. Terraform GCS Infrastructure
- **File**: `infra/main.tf`
  - Configures `terraform` required providers (`google >= 5.0`).
  - Defines `google_storage_bucket`:
    - `name = var.bucket_name`
    - `location = var.region`
    - `uniform_bucket_level_access = true`
    - `versioning { enabled = true }`
    - `lifecycle_rule`: expires noncurrent versions after 90 days.
- **File**: `infra/variables.tf`
  - Variables: `project_id`, `region` (default `europe-west1`), `bucket_name`, `environment` (default `dev`).
- **File**: `infra/outputs.tf`
  - Outputs: `bucket_name`, `bucket_url` (`gs://${google_storage_bucket.artifacts.name}`).
- **File**: `infra/terraform.tfvars.example`
  - Example variable assignments.

### 7. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add `issue_25: GCS artifact store & Terraform` marker to `[tool.pytest.ini_options]` `markers`.

### 8. Unit & Terraform Validation Tests
- **File**: `tests/unit/test_storage.py`
- **Change**: Write tests covering:
  - `test_fake_artifact_store_crud`: upload, download, download_text, exists, delete, list_keys.
  - `test_fake_artifact_store_upload_file`: uploads local file to fake store.
  - `test_fake_artifact_store_errors`: download missing key raises FileNotFoundError.
  - `test_gcs_artifact_store_mocked`: mocks GCS client/bucket/blob, verifies upload, download, delete, exists, list_keys, upload_file.
  - `test_storage_factory_resolution`: resolves FakeArtifactStore by default, GCSArtifactStore when bucket configured.
  - `test_terraform_files_and_syntax`: checks existence of `main.tf`, `variables.tf`, `outputs.tf`, verifies uniform access and versioning attributes, and runs `terraform fmt -check` if CLI available.
  Mark tests with `@pytest.mark.issue_25`.

### 9. Verification & Quality Gates
```bash
make test-issue ID=25
make check
```

### 10. Git & Issue Finish
```bash
make finish-issue ID=25 MSG="feat(storage): implement artifact store and terraform gcs bucket"
```

### 11. Milestone Finish (Closes M5)
```bash
make finish-milestone MILESTONE=M5
```

## Decisions
- **Unified interface with offline fake**: Following the repository's core pattern, `ArtifactStore` provides seamless parity between local offline execution (`FakeArtifactStore`) and production cloud runs (`GCSArtifactStore`).
- **Safe fallback factory**: `get_artifact_store()` defaults to `FakeArtifactStore` whenever `gcs_artifacts_bucket` is unset, ensuring all existing and future workflows run offline without external GCP credentials.
- **Cloud storage security**: Terraform enforces `uniform_bucket_level_access = true` and object versioning to protect critical backtest reports and model reasoning traces from accidental deletion or misconfiguration.
- **Milestone 5 completion**: Issue 25 is the 25th and final issue in the project roadmap, concluding Milestone 5 and delivering the complete autonomous trading platform.
