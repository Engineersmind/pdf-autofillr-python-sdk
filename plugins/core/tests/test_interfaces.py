"""Basic tests for pdf-autofiller-core interfaces."""

import pytest

from pdf_autofiller_core import HandlerInterface, StorageConfig, StorageInterface
from pdf_autofiller_core.interfaces.storage_interface import StorageProvider


def test_storage_interface_is_abstract():
    with pytest.raises(TypeError):
        StorageInterface(StorageConfig(provider=StorageProvider.LOCAL))


def test_handler_interface_is_abstract():
    with pytest.raises(TypeError):
        HandlerInterface()
