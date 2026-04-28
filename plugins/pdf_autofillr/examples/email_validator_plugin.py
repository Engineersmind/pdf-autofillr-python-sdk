"""
Example: Custom Email Validator Plugin

This example shows how to create a custom validator plugin.
"""

import re
from typing import Dict, Any, Optional
from pdf_autofiller_plugins import plugin
from pdf_autofiller_plugins.interfaces import ValidatorPlugin, PluginMetadata


@plugin(
    category="validator",
    name="email-validator",
    version="1.0.0",
    author="Example Team",
    description="Email address validator",
    tags=["email", "validation"],
)
class EmailValidatorPlugin(ValidatorPlugin):
    """
    Validator for email addresses.
    
    Validates:
    - Email format
    - Domain exists (optional)
    - No disposable emails (optional)
    """
    
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    DISPOSABLE_DOMAINS = {
        "tempmail.com",
        "throwaway.email",
        "guerrillamail.com",
    }
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="email-validator",
            version="1.0.0",
            author="Example Team",
            description="Email address validator",
            category="validator",
            tags=["email", "validation"],
        )
    
    def supports_field_type(self, field_type: str) -> bool:
        """Only supports email fields"""
        return field_type.lower() in ["email", "email_address", "emailaddress"]
    
    def validate(
        self,
        field_name: str,
        field_value: Any,
        rules: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Validate email address.
        
        Args:
            field_name: Field name
            field_value: Email address to validate
            rules: Optional validation rules
            
        Returns:
            Validation results
        """
        errors = []
        warnings = []
        
        # Check if value is string
        if not isinstance(field_value, str):
            errors.append("Email must be a string")
            return {
                "valid": False,
                "errors": errors,
                "warnings": warnings,
                "validator": "email-validator"
            }
        
        # Check email format
        if not self.EMAIL_REGEX.match(field_value):
            errors.append(f"Invalid email format: {field_value}")
        
        # Check for disposable email domains
        domain = field_value.split("@")[-1].lower()
        if domain in self.DISPOSABLE_DOMAINS:
            warnings.append(f"Disposable email domain detected: {domain}")
        
        # Check length
        if len(field_value) > 254:  # RFC 5321
            errors.append("Email address too long (max 254 characters)")
        
        # Apply custom rules if provided
        if rules:
            if rules.get("require_corporate") and domain in ["gmail.com", "yahoo.com", "hotmail.com"]:
                warnings.append("Personal email domain detected")
            
            if rules.get("allowed_domains"):
                if domain not in rules["allowed_domains"]:
                    errors.append(f"Domain not allowed: {domain}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "validator": "email-validator",
            "field_name": field_name,
            "field_value": field_value
        }
    
    def get_validation_rules(self) -> Dict[str, Any]:
        """Default validation rules"""
        return {
            "require_corporate": False,
            "allowed_domains": None,
            "block_disposable": True,
        }


# Example usage:
if __name__ == "__main__":
    from pdf_autofiller_plugins import PluginManager
    
    manager = PluginManager()
    manager.registry.register_plugin(EmailValidatorPlugin, "validator", "email-validator")
    
    plugin = manager.load_plugin("email-validator", "validator")
    
    # Test various emails
    test_emails = [
        "john@example.com",          # Valid
        "invalid.email",              # Invalid format
        "test@tempmail.com",          # Disposable
        "very.long." + "a" * 250 + "@example.com",  # Too long
    ]
    
    for email in test_emails:
        result = plugin.validate("email", email)
        status = "✓ Valid" if result["valid"] else "✗ Invalid"
        print(f"{status}: {email}")
        if result["errors"]:
            print(f"  Errors: {', '.join(result['errors'])}")
        if result["warnings"]:
            print(f"  Warnings: {', '.join(result['warnings'])}")
