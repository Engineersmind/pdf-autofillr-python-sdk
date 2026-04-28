"""
Example: Using the Plugin System

This example shows how to use the plugin system in your application.
"""

from pdf_autofiller_plugins import PluginManager


def main():
    """Example of using plugins"""
    
    # 1. Initialize plugin manager
    print("=== Initializing Plugin Manager ===")
    manager = PluginManager(
        plugin_paths=[
            "pdf_autofiller_plugins.builtin",  # Built-in plugins (if any)
            "examples",                          # Example plugins
            "user_plugins",                      # User plugins
        ],
        lazy_load=True  # Load plugins on-demand
    )
    
    # 2. Discover plugins
    print("\n=== Discovering Plugins ===")
    discovered = manager.discover_plugins(
        ["examples"],  # Search in examples directory
        categories=None  # All categories
    )
    
    for category, plugins in discovered.items():
        print(f"{category}: {', '.join(plugins)}")
    
    # 3. List all plugins
    print("\n=== Available Plugins ===")
    all_plugins = manager.list_plugins()
    for category, plugins in all_plugins.items():
        print(f"\n{category.upper()}:")
        for plugin_name in plugins:
            info = manager.get_plugin_info(plugin_name, category)
            if info:
                print(f"  - {info['name']} v{info['version']}: {info['description']}")
    
    # 4. Use extractor plugin
    print("\n=== Using Invoice Extractor ===")
    extractor = manager.find_extractor("sample_invoice.pdf")
    if extractor:
        print(f"Found extractor: {extractor.name}")
        result = extractor.extract("sample_invoice.pdf")
        print(f"Extracted {len(result['fields'])} fields")
        for field in result['fields'][:3]:  # Show first 3 fields
            print(f"  - {field['name']}: {field['value']}")
    else:
        print("No suitable extractor found")
    
    # 5. Use mapper plugin
    print("\n=== Using ML Mapper ===")
    extracted_fields = [
        {"name": "first_name", "value": "John"},
        {"name": "last_name", "value": "Doe"},
        {"name": "email", "value": "john@example.com"},
    ]
    
    mapper = manager.get_plugin("ml-mapper", "mapper")
    if mapper:
        result = mapper.map_fields(extracted_fields)
        print(f"Mapped fields: {result['mapped_fields']}")
        print(f"Confidence: {result.get('confidence', 0):.2%}")
    
    # 6. Use validator plugin
    print("\n=== Using Email Validator ===")
    validator = manager.get_plugin("email-validator", "validator")
    if validator:
        emails = [
            "john@example.com",
            "invalid.email",
            "test@tempmail.com",
        ]
        
        for email in emails:
            result = validator.validate("email", email)
            status = "✓" if result["valid"] else "✗"
            print(f"  {status} {email}")
            if result["errors"]:
                print(f"    Errors: {', '.join(result['errors'])}")
    
    # 7. Plugin lifecycle
    print("\n=== Plugin Lifecycle ===")
    plugin = manager.load_plugin("invoice-extractor", "extractor")
    print(f"Loaded: {plugin.name} (initialized: {plugin.is_initialized})")
    
    manager.unload_plugin("invoice-extractor", "extractor")
    print("Unloaded plugin")
    
    # 8. Cleanup
    print("\n=== Shutting Down ===")
    manager.shutdown()
    print("All plugins shut down")


if __name__ == "__main__":
    main()
