from ragpdf.correctors.base import FieldCorrectorBackend


class CorrectorFactory:
    @staticmethod
    def create() -> FieldCorrectorBackend:
        from ragpdf.config.settings import RAGPDF_CORRECTOR_BACKEND
        if RAGPDF_CORRECTOR_BACKEND == "anthropic":
            from ragpdf.correctors.anthropic_corrector import AnthropicCorrectorBackend
            return AnthropicCorrectorBackend()

        if RAGPDF_CORRECTOR_BACKEND == "litellm":
            from ragpdf.correctors.litellm_corrector import LiteLLMCorrectorBackend
            return LiteLLMCorrectorBackend()

        if RAGPDF_CORRECTOR_BACKEND == "noop":
            from ragpdf.correctors.noop_corrector import NoOpCorrectorBackend
            return NoOpCorrectorBackend()

        from ragpdf.correctors.openai_corrector import OpenAICorrectorBackend
        return OpenAICorrectorBackend()
