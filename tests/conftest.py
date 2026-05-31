"""Shared test fixtures."""

import pytest
from pathlib import Path

from app.models.policy import PolicyTerms
from app.policy.loader import load_policy


@pytest.fixture
def policy() -> PolicyTerms:
    """Load the policy terms for tests."""
    # Try multiple paths to find policy_terms.json
    candidates = [
        Path(__file__).parent.parent.parent / "policy_terms.json",
        Path(__file__).parent.parent / "policy_terms.json",
        Path("policy_terms.json"),
    ]
    for p in candidates:
        if p.exists():
            return load_policy(str(p))
    raise FileNotFoundError("Cannot find policy_terms.json for tests")
