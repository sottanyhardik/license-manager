"""Test configuration and environment setup."""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
TEST_ROOT = PROJECT_ROOT / "tests"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

# Environment setup
BASE_URL = os.getenv("LM_BASE_URL", "http://localhost:5173")
TEST_USERNAME = os.getenv("LM_TEST_USERNAME", "admin")
TEST_PASSWORD = os.getenv("LM_TEST_PASSWORD", "admin")

# Test environment detection
ENVIRONMENT = os.getenv("LM_ENVIRONMENT", "development")

# Selenium configuration
CHROME_OPTIONS = {
    "start_maximized": True,
    "disable_notifications": True,
    "no_sandbox": True,
    "disable_dev_shm_usage": True,
}

# Test data
TEST_DATA_PREFIX = "SELENIUM_TEST_"


@dataclass
class TestDataRecord:
    """Tracks test data for cleanup."""
    entity: str
    id: any
    created_by_test: bool = True
    cleanup_required: bool = True
    original_state: Optional[dict] = None


class TestRegistry:
    """Manages test data lifecycle."""
    def __init__(self):
        self.created_records = []
        self.modified_records = []
        self.deleted_records = []

    def register_created(self, entity: str, id: any, original_state: dict = None):
        """Register a created record."""
        record = TestDataRecord(
            entity=entity,
            id=id,
            created_by_test=True,
            original_state=original_state
        )
        self.created_records.append(record)
        return record

    def register_modified(self, entity: str, id: any, original_state: dict):
        """Register a modified record for restoration."""
        record = TestDataRecord(
            entity=entity,
            id=id,
            created_by_test=False,
            original_state=original_state
        )
        self.modified_records.append(record)
        return record

    def cleanup_summary(self):
        """Get cleanup summary."""
        return {
            "created": len(self.created_records),
            "modified": len(self.modified_records),
            "deleted": len(self.deleted_records),
            "created_records": self.created_records,
            "modified_records": self.modified_records,
        }


# Global test registry
test_registry = TestRegistry()
