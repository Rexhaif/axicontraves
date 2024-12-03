# List available commands
default:
    @just --list

# Install development dependencies and setup project
setup:
    poetry install
    poetry run maturin develop

# Build and install in development mode
dev:
    poetry run maturin develop

# Run tests
test:
    poetry run pytest tests/

# Clean build artifacts only
clean-artifacts:
    rm -rf target/
    rm -rf dist/
    rm -rf *.egg-info/
    rm -rf .pytest_cache/
    find axicontraves tests -type d -name "__pycache__" -exec rm -rf {} +
    rm -rf axicontraves/*.so
    rm -rf axicontraves/*.dylib
    rm -rf axicontraves/*.pyd

# Clean everything including Poetry environment (use with caution)
clean-all: clean-artifacts
    poetry env remove --all

# Clean test environments older than 7 days
clean-old-test-envs:
    #!/usr/bin/env bash
    find ~/.axicontraves/test_environments -maxdepth 1 -type d -mtime +7 -exec rm -rf {} +

# Clean all test environments
clean-test-envs:
    rm -rf ~/.axicontraves/test_environments/*

# Clean build artifacts and test environments
clean: clean-artifacts clean-test-envs
    @echo "Cleaned build artifacts and test environments"

# Clean everything and start fresh
reset: clean-all
    just setup

# Build production wheel for current platform
build:
    poetry run maturin build --release

# Build universal2 wheel for macOS (both Intel and Apple Silicon)
build-universal-macos:
    poetry run maturin build --release -i python3 --target universal2-apple-darwin

# Test the production wheel
test-prod: build
    #!/usr/bin/env bash
    # Prepare test environment directory
    mkdir -p ~/.axicontraves/test_environments
    TEST_DIR=~/.axicontraves/test_environments/test_$(date +%Y%m%d_%H%M%S)
    
    # Create and run tests in a fresh environment
    mkdir -p $TEST_DIR && cd $TEST_DIR && \
    poetry init --name axicontraves-test --description "Test environment for axicontraves" \
        --author "Test <test@test.com>" --python ">=3.8" --dependency pytest --no-interaction && \
    poetry env use python3 && \
    poetry add {{invocation_directory()}}/target/wheels/axicontraves-*.whl && \
    poetry run pytest {{invocation_directory()}}/tests/
    
    # Keep the last 5 test environments for debugging
    ls -t ~/.axicontraves/test_environments | tail -n +6 | xargs -I {} rm -rf ~/.axicontraves/test_environments/{}

# Full release workflow (keeps dev environment)
release: clean-artifacts setup build test-prod
    @echo "Release build completed and tested successfully"
    @echo "To publish to PyPI, run: just publish"

# Publish to PyPI (requires PyPI credentials)
publish:
    #!/usr/bin/env bash
    if [ -z "$PYPI_TOKEN" ]; then
        echo "Error: PYPI_TOKEN environment variable not set"
        echo "Please set it with your PyPI API token"
        exit 1
    fi
    poetry config pypi-token.pypi $PYPI_TOKEN
    poetry run maturin upload --skip-existing target/wheels/*

# Development workflow - rebuild and test after changes
watch:
    #!/usr/bin/env bash
    while true; do
        clear
        just dev
        just test
        echo "Watching for changes... (Ctrl+C to stop)"
        sleep 2
    done

# Update dependencies
update:
    poetry update
    just dev

# Show current environment info
info:
    poetry env info
    poetry show
    @echo "\nProduction test environments:"
    @ls -lht ~/.axicontraves/test_environments 2>/dev/null || echo "No test environments found"

# Create or recreate development environment
reset-dev: clean-artifacts
    poetry install --sync
    just dev