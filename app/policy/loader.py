"""Load and cache policy terms from JSON file."""

import json
from pathlib import Path
from functools import lru_cache

from app.models.policy import PolicyTerms


@lru_cache(maxsize=1)
def load_policy(file_path: str = None) -> PolicyTerms:
    """Load policy terms from JSON. Cached after first call."""
    if file_path is None:
        # Try multiple paths
        candidates = [
            Path("policy_terms.json"),
            Path("../policy_terms.json"),
            Path(__file__).parent.parent.parent.parent / "policy_terms.json",
        ]
        for p in candidates:
            if p.exists():
                file_path = str(p)
                break
        else:
            raise FileNotFoundError("policy_terms.json not found")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return PolicyTerms(**data)


def get_member(policy: PolicyTerms, member_id: str):
    """Look up a member by ID."""
    for member in policy.members:
        if member.member_id == member_id:
            return member
    return None
