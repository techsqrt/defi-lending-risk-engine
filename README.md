# Aave Risk Monitor

Aave v3 risk monitoring demo.

## Prerequisites

- Node.js 20.x
- Python 3.10.x
- pnpm
- Poetry
- Docker & Docker Compose

## Quick Start

```bash
# Install all dependencies
./install.sh

# Start all services (docker, api, web)
./run.sh

# Run all tests
./test.sh
```

## Services

- **Web**: http://localhost:3000
- **API**: http://127.0.0.1:8000

## Python Import Style

This project uses absolute imports from the repository root (Google style). Always use full paths:

```python
# Correct
from services.api.src.api.main import app

# Incorrect (relative imports)
from .main import app
from api.main import app
```

### IDE Setup

Add the repo root to your Python path for proper IDE support:

**VS Code** (`.vscode/settings.json`):
```json
{
  "python.analysis.extraPaths": ["${workspaceFolder}"]
}
```

**PyCharm**: Right-click the repo root folder → Mark Directory as → Sources Root

**Shell** (for manual runs):
```bash
export PYTHONPATH="$(pwd)"
```
