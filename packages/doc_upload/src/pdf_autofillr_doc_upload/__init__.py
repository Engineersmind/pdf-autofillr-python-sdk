# pdf_autofillr_doc_upload/__init__.py
"""
pdf-autofillr-doc-upload SDK

Extract structured data from documents (PDF, DOCX, PPTX, XLSX, CSV, JSON, MD, TXT)
using an LLM, then optionally fill a blank PDF via the mapper module.

Quick start::

    from pdf_autofillr_doc_upload import DocUploadClient

    client = DocUploadClient()
    result = client.run(
        document_path="investor_profile.pdf",
        schema_path="configs/form_keys.json",
        output_path="output/filled.json",
    )
"""

from pdf_autofillr_doc_upload.client import DocUploadClient
from pdf_autofillr_doc_upload.config.settings import DocUploadSettings
from pdf_autofillr_doc_upload.pdf.inprocess_filler import InProcessMapperFiller
from pdf_autofillr_doc_upload.pdf.interface import PDFFillerInterface
from pdf_autofillr_doc_upload.pdf.mapper_filler import MapperPDFFiller
from pdf_autofillr_doc_upload.storage.azure_storage import AzureStorage
from pdf_autofillr_doc_upload.storage.gcp_storage import GCSStorage
from pdf_autofillr_doc_upload.storage.local_storage import LocalStorage
from pdf_autofillr_doc_upload.storage.s3_storage import S3Storage

__version__ = "0.1.5"


def copy_sample_configs(destination: str = ".") -> None:
    """
    Copy bundled sample configs to destination/configs/.

    Run once after install::

        python -c "import pdf_autofillr_doc_upload; pdf_autofillr_doc_upload.copy_sample_configs('.')"
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
    print(f"✅ Extractor configs copied to: {dst.resolve()}")

    try:
        import pdf_autofillr_mapper

        pdf_autofillr_mapper.copy_sample_configs(destination)
        print("✅ Mapper config (mapper_config.ini) also copied.")
    except ImportError:
        pass  # intentional
    except Exception as e:
        print(f"   Note: could not copy mapper config: {e}")

    print("\n   Edit configs/ to customise your schema and mapper settings.")


__all__ = [
    "DocUploadClient",
    "LocalStorage",
    "S3Storage",
    "GCSStorage",
    "AzureStorage",
    "DocUploadSettings",
    "PDFFillerInterface",
    "MapperPDFFiller",
    "InProcessMapperFiller",
    "copy_sample_configs",
    "__version__",
]
