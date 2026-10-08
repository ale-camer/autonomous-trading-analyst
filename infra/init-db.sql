-- Enable pgvector extension in the primary trading database
CREATE EXTENSION IF NOT EXISTS vector;

-- Create dedicated metadata database for Apache Airflow
CREATE DATABASE airflow;

-- Grant all privileges on airflow database to trader user
GRANT ALL PRIVILEGES ON DATABASE airflow TO trader;
