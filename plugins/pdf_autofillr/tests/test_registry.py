"""Basic tests for pdf-autofiller-plugins."""

from pdf_autofiller_plugins import PluginManager, PluginRegistry


def test_plugin_manager_instantiation():
    manager = PluginManager()
    assert manager is not None


def test_plugin_registry_instantiation():
    registry = PluginRegistry()
    assert registry is not None
