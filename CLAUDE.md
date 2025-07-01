# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HeatWave CLI is a command-line tool for Oracle MySQL HeatWave POC demonstrations. It manages database connections and OCI authentication with encrypted credential storage.

## Development Setup

This project uses `uv` for dependency management. Key commands:

```bash
# Install in development mode
uv pip install -e .

# Run the CLI
uv run heatwaved [command]

# Lint code (automatically fixes issues)
ruff check heatwaved/ --fix

# Add new dependencies
uv add [package-name]

# Add dev dependencies
uv add --dev [package-name]
```

## Architecture

### Core Components

1. **CLI Entry Point** (`heatwaved/main.py`): Uses Typer to define the command structure with three main command groups: `init`, `test`, and `config`.

2. **Configuration Management** (`heatwaved/config/manager.py`):
   - Handles all configuration storage in `.heatwaved/` directory
   - Encrypts passwords using Fernet encryption before storage
   - Creates `.gitignore` automatically to protect sensitive files
   - Important: `save_db_config()` and `save_oci_config()` make copies of input dicts to avoid modifying them

3. **Command Structure**:
   - `init`: Full setup flow (DB + optional OCI), or individual `init db`/`init oci`
   - `test`: Connection testing with automatic credential decryption
   - `config`: View current configuration
   - `schema`: Database schema management (create, list, drop, use)
   - `genai`: HeatWave GenAI permission setup (setup, check)
   - `lakehouse`: HeatWave Lakehouse Dynamic Group/Policy management (setup, list-buckets)

### Key Design Decisions

- **Password Encryption**: Database passwords are encrypted immediately when saved. The `save_db_config` method copies the config dict to prevent the original password from being encrypted in-place.
- **OCI Key Management**: Private key files are automatically copied into `.heatwaved/.oci/` and the config file is updated with the new path.
- **Test After Setup**: Both database and OCI configurations automatically test connections after setup to provide immediate feedback.

## Commit Convention

This project follows Conventional Commits 1.0.0 (see COMMIT.md). Use prefixes:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation
- `chore:` for maintenance tasks

## Important Implementation Notes

1. **Connection Testing**: When testing database connections during init, use the original config dict with plain text password, not the saved version which has encrypted password.

2. **OCI Config Parsing**: The OCI configuration is pasted as multi-line input. The code collects lines until two consecutive empty lines are entered.

3. **Error Handling**: Database connection errors are categorized:
   - "Access denied" → Authentication failed
   - "Can't connect" or "not resolve" → Connection failed
   - Other → Generic database error

4. **Ruff Configuration**: Line length is set to 100 characters. The linter is configured to use Python 3.11+ features.