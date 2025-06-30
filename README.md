# HeatWave CLI

A command-line interface tool for Oracle MySQL HeatWave POC demonstrations. This tool simplifies database connections, OCI authentication setup, and provides easy access to HeatWave features for proof-of-concept demonstrations.

## Features

- Secure database connection management with encrypted password storage
- OCI (Oracle Cloud Infrastructure) authentication configuration
- Automatic connection testing after setup
- Schema (database) management commands
- HeatWave GenAI permission setup automation
- Designed specifically for HeatWave POC demonstrations
- Local configuration storage with encryption

## Installation

### Prerequisites

- Python 3.11 or higher
- MySQL HeatWave instance
- OCI account (for Lakehouse features)

### Install from PyPI (Coming Soon)

```bash
pip install heatwaved-cli
```

### Install from Source

```bash
git clone https://github.com/afininc/heatwaved-cli.git
cd heatwaved-cli
pip install -e .
```

### Using uv (Recommended for Development)

```bash
git clone https://github.com/afininc/heatwaved-cli.git
cd heatwaved-cli
uv pip install -e .
```

## Quick Start

### 1. Complete Setup (Database + OCI)

Initialize both database and OCI configuration:

```bash
heatwaved init
```

This will:
- Prompt for database connection details
- Test the database connection
- Ask if you want to configure OCI
- Test OCI authentication if configured

### 2. Database-Only Setup

```bash
heatwaved init db
```

### 3. OCI-Only Setup (Requires existing database configuration)

```bash
heatwaved init oci
```

## Configuration

### Database Configuration

When running `heatwaved init` or `heatwaved init db`, you'll be prompted for:

- **DB Host**: Your MySQL HeatWave instance hostname
- **DB Port**: Database port (default: 3306)
- **Username**: Database username
- **Password**: Database password (stored encrypted)

### OCI Configuration

For OCI setup, you'll need to:

1. Generate API keys in OCI Console:
   - Visit: https://cloud.oracle.com/identity/domains/my-profile/auth-tokens
   - Go to API keys -> Add API key

2. Copy the configuration from OCI Console and paste when prompted

3. Provide the path to your private key file (will be copied to the project)

## Commands

### Initialize Configuration

```bash
# Complete setup (DB + OCI)
heatwaved init

# Database only
heatwaved init db

# OCI only (requires existing DB config)
heatwaved init oci
```

### Test Connections

```bash
# Test both database and OCI
heatwaved test

# Test database only
heatwaved test --db

# Test OCI only
heatwaved test --oci
```

### View Configuration

```bash
# Show current configuration
heatwaved config show

# Show configuration directory path
heatwaved config path
```

### Manage Schemas

```bash
# Create a new schema
heatwaved schema create my_database

# List all schemas
heatwaved schema list

# List schemas matching pattern
heatwaved schema list --pattern "test%"

# Drop a schema (with confirmation)
heatwaved schema drop my_database

# Drop a schema without confirmation
heatwaved schema drop my_database --force

# Set default schema for future operations
heatwaved schema use my_database
```

### HeatWave GenAI Setup

```bash
# Set up GenAI permissions for a schema
heatwaved genai setup my_schema

# Set up with different input/output schemas
heatwaved genai setup main_schema --input-schema source_data --output-schema results

# Preview SQL statements without executing
heatwaved genai setup my_schema --show-only

# Check current user's GenAI permissions
heatwaved genai check
```

## Configuration Storage

All configuration is stored locally in the `.heatwaved/` directory:

```
.heatwaved/
├── config.json      # Encrypted database credentials and settings
├── .key            # Encryption key (auto-generated)
└── .oci/
    └── config      # OCI configuration file
```

**Important**: The `.heatwaved/` directory contains sensitive information and is automatically excluded from git.

## Security

- Database passwords are encrypted using Fernet encryption
- Configuration files are stored locally only
- The `.heatwaved/` directory is git-ignored by default
- Private keys are copied to the local configuration directory

## Troubleshooting

### Database Connection Failed

- Verify your MySQL HeatWave instance is running
- Check network connectivity to the database host
- Ensure the username and password are correct
- Verify the port number (default is 3306)

### OCI Authentication Failed

- Ensure your API key is properly generated in OCI Console
- Verify the private key file path is correct
- Check that the key file has proper permissions
- Ensure your OCI user has necessary permissions

### Configuration Not Found

If you see "HeatWave configuration not found", run:
```bash
heatwaved init
```

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/afininc/heatwaved-cli.git
cd heatwaved-cli

# Install with development dependencies
uv pip install -e .
uv add --dev ruff

# Run linting
ruff check heatwaved/

# Run with auto-fix
ruff check heatwaved/ --fix
```

### Project Structure

```
heatwaved-cli/
├── heatwaved/
│   ├── commands/       # CLI commands
│   │   ├── init.py    # Initialization commands
│   │   ├── test.py    # Connection testing
│   │   └── config.py  # Configuration management
│   ├── config/        # Configuration utilities
│   │   └── manager.py # Config file management
│   └── main.py        # CLI entry point
├── pyproject.toml     # Project configuration
└── README.md          # This file
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes following [Conventional Commits](https://www.conventionalcommits.org/)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Support

For issues and feature requests, please visit:
https://github.com/afininc/heatwaved-cli/issues

## Authors

- Ryan Kwon - ryankwon@a-fin.co.kr

---

Built for Oracle MySQL HeatWave POC demonstrations