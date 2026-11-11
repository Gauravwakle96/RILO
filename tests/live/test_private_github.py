"""Opt-in live acceptance for authorized private GitHub ingestion."""

import os

import pytest
from rilo.ingestion import github_repository


@pytest.mark.asyncio
async def test_private_github_capture_is_commit_pinned_and_bounded():
    token = os.environ.get("GITHUB_TOKEN", "")
    repository = os.environ.get("RILO_TEST_PRIVATE_GITHUB_REPOSITORY", "")
    if not token or not repository:
        pytest.skip("Set GITHUB_TOKEN and RILO_TEST_PRIVATE_GITHUB_REPOSITORY for live acceptance.")
    sources, metadata = await github_repository(
        repository, token, file_limit=50, byte_limit=2_000_000
    )
    assert sources
    assert len(metadata["commit_sha"]) == 40
    assert metadata["retrieval"] == "commit-pinned bounded source files"
    assert metadata["files_captured"] <= 50
    assert metadata["selected_bytes"] <= 2_000_000
    assert token not in str(metadata) and token not in str(sources)
