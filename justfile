set shell := ["bash", "-cu"]

app_dir := "src/app"
app_path := "app:app"
openapi_file := "openapi_schema.json"
api_docs_file := "API.md"

# List available commands
default:
    just --list

# Start the Litestar app for local development
dev:
    uv run litestar --app-dir {{app_dir}} --app={{app_path}} run --reload --debug

# Sync uv environment including dev dependencies
sync:
    uv sync --dev

# Generate OpenAPI JSON and Markdown API docs
api-docs:
    uv run litestar --app-dir {{app_dir}} --app={{app_path}} schema openapi --output {{openapi_file}}
    uv run openapi2markdown {{openapi_file}} {{api_docs_file}}

# Sync dev dependencies, then generate API docs
docs: sync api-docs