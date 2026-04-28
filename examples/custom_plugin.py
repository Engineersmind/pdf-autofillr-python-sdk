"""
Plugins — write and register a custom validator.

Requires: pip install pdf-autofiller-plugins
"""
import re
from pdf_autofiller_plugins import plugin, PluginManager
from pdf_autofiller_plugins.interfaces import ValidatorPlugin


@plugin(
    category="validator",
    name="us-phone-validator",
    version="1.0.0",
    description="Validates US phone numbers",
)
class USPhoneValidatorPlugin(ValidatorPlugin):
    PATTERN = re.compile(r"^\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$")

    def validate(self, field_name, value, context):
        valid = bool(self.PATTERN.match(value.strip()))
        return {
            "valid": valid,
            "error": None if valid else f"'{value}' is not a valid US phone number",
        }


if __name__ == "__main__":
    manager = PluginManager()
    manager.load_plugin(USPhoneValidatorPlugin)

    for v in ["+1 (555) 123-4567", "555.123.4567", "not-a-phone"]:
        r = manager.run_validators("phone", v, context={})
        print(f"  {v!r:25} {'✓' if r[0]['valid'] else '✗'}")
