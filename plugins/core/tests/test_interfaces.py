"""Basic tests for pdf-autofiller-core interfaces."""

import pytest
from pdf_autofiller_core import StorageInterface, HandlerInterface


def test_storage_interface_is_abstract():
    with pytest.raises(TypeError):
        StorageInterface()


def test_handler_interface_is_abstract():
    with pytest.raises(TypeError):
        HandlerInterface()
