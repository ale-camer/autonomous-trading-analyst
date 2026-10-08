output "bucket_name" {
  description = "Name of the provisioned GCS artifacts bucket."
  value       = google_storage_bucket.artifacts.name
}

output "bucket_url" {
  description = "Google Cloud Storage URI for the provisioned bucket."
  value       = "gs://${google_storage_bucket.artifacts.name}"
}

output "bucket_self_link" {
  description = "URI of the created GCS bucket resource."
  value       = google_storage_bucket.artifacts.self_link
}
