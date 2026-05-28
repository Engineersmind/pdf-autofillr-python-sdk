"""
Tests for copy_sample_configs() — verifies bundled config files are shipped correctly.
"""


def test_copy_sample_configs_creates_configs_dir(tmp_path):
    """copy_sample_configs should create configs/ in the destination."""
    import pdf_autofillr_mapper

    pdf_autofillr_mapper.copy_sample_configs(str(tmp_path))
    assert (tmp_path / "configs").is_dir()


def test_copy_sample_configs_includes_mapper_ini(tmp_path):
    """mapper_config.ini should be present after copy."""
    import pdf_autofillr_mapper

    pdf_autofillr_mapper.copy_sample_configs(str(tmp_path))
    assert (tmp_path / "configs" / "mapper_config.ini").exists()


def test_copy_sample_configs_includes_env_example(tmp_path):
    """env.mapper.example should be present after copy."""
    import pdf_autofillr_mapper

    pdf_autofillr_mapper.copy_sample_configs(str(tmp_path))
    assert (tmp_path / "configs" / ".env.mapper.example").exists()


def test_copy_sample_configs_is_idempotent(tmp_path):
    """Calling copy_sample_configs twice should not raise."""
    import pdf_autofillr_mapper

    pdf_autofillr_mapper.copy_sample_configs(str(tmp_path))
    pdf_autofillr_mapper.copy_sample_configs(str(tmp_path))  # second call
    assert (tmp_path / "configs" / "mapper_config.ini").exists()


def test_mapper_config_ini_content_is_valid(tmp_path):
    """mapper_config.ini must have required sections."""
    import configparser

    import pdf_autofillr_mapper

    pdf_autofillr_mapper.copy_sample_configs(str(tmp_path))
    ini = configparser.ConfigParser()
    ini.read(tmp_path / "configs" / "mapper_config.ini")
    assert ini.has_section("general")
    assert ini.has_section("mapping")
    assert ini.has_section("local")
    assert ini.get("mapping", "llm_model") == "gpt-4o"
