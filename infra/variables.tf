variable "project_id" {
  description = "The Google Cloud Platform project ID."
  type        = string
}

variable "region" {
  description = "GCP region where storage resources are provisioned."
  type        = string
  default     = "europe-west1"
}

variable "bucket_name" {
  description = "Globally unique name for the GCS artifacts bucket."
  type        = string
}

variable "storage_class" {
  description = "Storage class of the GCS bucket."
  type        = string
  default     = "STANDARD"
}

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "force_destroy" {
  description = "When true, bucket can be deleted even if non-empty (useful for non-prod environments)."
  type        = bool
  default     = true
}
