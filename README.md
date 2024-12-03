# Axicontraves

A Python library with Rust extensions using PyO3.

## Prerequisites

1. Install Rust (if not already installed):
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   ```

2. Install Poetry (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. Install Just command runner:
   ```bash
   # On macOS
   brew install just

   # On Linux
   curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash
   ```

## Development

The project uses `just` for managing development tasks. To see available commands:

```bash
just
```

Common workflows:

1. Initial setup:
   ```bash
   just setup
   ```

2. Development build and test:
   ```bash
   just dev
   just test
   ```

3. Watch mode (auto-rebuild on changes):
   ```bash
   just watch
   ```

4. Show environment info:
   ```bash
   just info
   ```

5. Update dependencies:
   ```bash
   just update
   ```

## Environment Management

The project maintains a persistent Poetry environment for IDE integration:

- `just setup` - Initial environment setup
- `just reset-dev` - Recreate development environment from scratch
- `just clean` - Clean build artifacts (keeps dev environment)
- `just clean-all` - Clean everything including dev environment (use with caution)

## Production Build

To create and test a production build:

```bash
# Full release workflow (clean artifacts, build, test)
just release

# Individual steps:
just clean-artifacts  # Clean build artifacts only
just build           # Build production wheel
just test-prod       # Test the production wheel

# For macOS universal2 build (Intel + Apple Silicon):
just build-universal-macos
```

## Publishing

1. Set your PyPI token:
   ```bash
   export PYPI_TOKEN="your-token-here"
   ```

2. Publish to PyPI:
   ```bash
   just publish
   ```

## Usage

```python
from axicontraves import add_numbers

result = add_numbers(2, 3)  # Returns 5
```

## Development Commands

- `just setup` - Install dependencies and set up the project
- `just dev` - Build and install in development mode
- `just test` - Run tests
- `just watch` - Watch for changes and rebuild/test automatically
- `just clean` - Clean build artifacts (keeps dev environment)
- `just clean-all` - Clean everything including dev environment
- `just clean-artifacts` - Clean only build artifacts
- `just build` - Build production wheel
- `just test-prod` - Test production wheel
- `just update` - Update dependencies and rebuild
- `just info` - Show environment information
- `just reset-dev` - Recreate development environment
