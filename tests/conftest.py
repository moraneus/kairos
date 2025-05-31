# tests/conftest.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Test configuration and shared fixtures for pytest

"""Test configuration and shared fixtures for Kairos PBTL monitoring tests.

This module provides pytest configuration, fixtures, and utilities for testing
the PBTL runtime verification system. It ensures proper module path setup
and provides common test infrastructure for all test modules.

The configuration handles:
- Python path setup for module imports
- Test environment initialization
- Common fixtures for monitoring components
- Test session management
"""

import sys
import os
import pytest
from pathlib import Path

# Ensure project modules can be imported
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Initialize test environment and verify module availability.

    Automatically runs before any tests to ensure the testing environment
    is properly configured. Validates that core modules can be imported
    and skips the entire test session if critical dependencies are missing.

    Yields:
        None: Control to test execution

    Raises:
        pytest.skip: If required modules cannot be imported
    """
    # Verify core modules are importable
    try:
        import core
        import parser
        import utils
    except ImportError as e:
        pytest.skip(f"Cannot import required modules: {e}")

    # Test environment is ready
    yield

    # Cleanup operations (if needed)
    pass


@pytest.fixture
def sample_processes():
    """Provide standard process set for testing.

    Returns:
        List[str]: Common process identifiers for test scenarios
    """
    return ["P1", "P2", "P3"]


@pytest.fixture
def basic_formula():
    """Provide basic PBTL formula for testing.

    Returns:
        str: Simple PBTL formula for basic tests
    """
    return "EP(p)"


@pytest.fixture
def complex_formula():
    """Provide complex PBTL formula for advanced testing.

    Returns:
        str: Complex PBTL formula for comprehensive tests
    """
    return "EP(EP(p) & EP(q) & !EP(r))"
