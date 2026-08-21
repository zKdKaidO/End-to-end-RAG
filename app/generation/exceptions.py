class GenerationError(Exception):
    def __init__(self, stage: str, error_code: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.error_code = error_code
        self.message = message


class GenerationValidationError(GenerationError):
    pass


class GenerationDependencyError(GenerationError):
    pass


class GenerationTimeoutError(GenerationError):
    pass


class GenerationConfigurationError(GenerationError):
    pass
