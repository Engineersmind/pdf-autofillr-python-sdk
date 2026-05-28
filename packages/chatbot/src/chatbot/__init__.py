# chatbot/src/chatbot/__init__.py
"""
pdf-autofillr-chatbot SDK
"""

from chatbot.client import chatbotClient
from chatbot.config.form_config import FormConfig
from chatbot.pdf.fill_report import FillReport
from chatbot.pdf.interface import PDFFillerInterface
from chatbot.pdf.mapper_filler import MapperPDFFiller
from chatbot.storage.azure_storage import AzureStorage
from chatbot.storage.gcp_storage import GCSStorage
from chatbot.storage.local_storage import LocalStorage
from chatbot.storage.s3_storage import S3Storage

__version__ = "0.3.0"


def copy_sample_configs(destination: str = ".") -> None:
    """
    Copy bundled sample configs to destination/configs/.

    Copies:
        configs/form_keys.json
        configs/mandatory.json
        configs/meta_form_keys.json
        configs/field_questions.json
        configs/form_keys_label.json
        configs/global_investor_type_keys/
        configs/mapper_config.ini

    Run once after pip install::

        python -c "import chatbot; chatbot.copy_sample_configs('.')"
    """
    import shutil
    from pathlib import Path

    src = Path(__file__).parent / "config_samples"
    if not src.exists():
        src = Path(__file__).parent.parent.parent / "config_samples"
    if not src.exists():
        raise FileNotFoundError(
            f"config_samples not found at {src}. Reinstall the package."
        )

    dst = Path(destination) / "configs"
    shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
    print(f"✅ Chatbot configs copied to: {dst.resolve()}")

    try:
        import pdf_autofillr_mapper

        pdf_autofillr_mapper.copy_sample_configs(destination)
        print("✅ Mapper config (mapper_config.ini) also copied.")
    except ImportError:
        pass
    except Exception as e:
        print(f"   Note: could not copy mapper config: {e}")

    print(
        "\n   Edit files in configs/ to customise your form fields and mapper settings."
    )


__all__ = [
    "chatbotClient",
    "LocalStorage",
    "S3Storage",
    "GCSStorage",
    "AzureStorage",
    "FormConfig",
    "PDFFillerInterface",
    "MapperPDFFiller",
    "FillReport",
    "copy_sample_configs",
]
