# tests/unit/test_find_by_name.py
"""
Tests for VectorStoreBackend.find_by_name() — used by FeedbackPipeline
to route errors to the correct vector without hardcoding file paths.
"""
import pytest
import tempfile
import os
from ragpdf.vector_stores.local_vector_store import LocalVectorStore


@pytest.fixture
def store(tmp_path):
    s = LocalVectorStore(path=str(tmp_path))
    s.add_vector(
        field_name="investor_full_name",
        context="Full legal name",
        section_context="Personal Info",
        headers=["Section 1"],
        embedding=[0.1] * 384,
    )
    s.add_vector(
        field_name="investor_email",
        context="Email address",
        section_context="Contact",
        headers=["Section 2"],
        embedding=[0.2] * 384,
    )
    s.save()
    return s


def test_find_by_name_found(store):
    vid = store.find_by_name("investor_full_name")
    assert vid is not None
    assert vid.startswith("vec_")


def test_find_by_name_second_entry(store):
    vid = store.find_by_name("investor_email")
    assert vid is not None


def test_find_by_name_not_found(store):
    vid = store.find_by_name("nonexistent_field")
    assert vid is None


def test_find_by_name_empty_string(store):
    vid = store.find_by_name("")
    assert vid is None


def test_find_by_name_returns_correct_id(store):
    # Add a known vector and verify the returned ID is consistent
    vid_added = store.add_vector(
        field_name="unique_test_field",
        context="test",
        section_context="test",
        headers=[],
        embedding=[0.5] * 384,
    )
    vid_found = store.find_by_name("unique_test_field")
    assert vid_found == vid_added
