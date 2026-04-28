"""
pdf-autofillr-mapper
====================
PDF field extraction, semantic mapping, embedding and filling engine.

Quick start::

    from pdf_autofillr_mapper import PDFPipeline, MapperConfig, copy_sample_configs

    # 1. Copy sample configs once (run once after pip install)
    copy_sample_configs(".")

    # 2. Build config
    cfg = MapperConfig.from_directory("./configs")

    # 3. Run the pipeline
    import asyncio
    pipeline = PDFPipeline(mapper_config=cfg)
    result = asyncio.run(pipeline.run_all(
        input_pdf_path="./blank_form.pdf",
        input_data_path="./configs/form_keys.json",
    ))
    print(result["final_output"])  # path to filled PDF
"""
from __future__ import annotations

from pdf_autofillr_mapper.orchestrator import PDFPipeline
from pdf_autofillr_mapper.config.mapper_config import MapperConfig

__version__ = "1.0.7"
__all__ = ["PDFPipeline", "MapperConfig", "copy_sample_configs"]


def copy_sample_configs(destination: str = ".") -> None:
    """
    Copy bundled mapper sample configs to destination/configs/.

    Run once after pip install::

        python -c "import pdf_autofillr_mapper; pdf_autofillr_mapper.copy_sample_configs('.')"

    Copies:
        configs/mapper_config.ini     — LLM model, chunking, storage paths
        configs/.env.mapper.example   — API key template

    When using alongside pdf-autofillr-chatbot, the chatbot's
    copy_sample_configs() calls this automatically.
    """
    import shutil
    from pathlib import Path

    src = Path(__file__).parent / "config_samples"
    if not src.exists():
        raise FileNotFoundError(
            f"config_samples not found at {src}. "
            "Reinstall with: pip install --force-reinstall pdf-autofillr-mapper"
        )

    dst = Path(destination) / "configs"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
    print(f"Mapper configs copied to: {dst.resolve()}")
    print("  Edit configs/mapper_config.ini to configure LLM model, storage paths, etc.")
