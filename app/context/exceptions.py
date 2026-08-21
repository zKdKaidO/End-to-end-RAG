class ContextBuilderError(Exception):
    def __init__(self, stage: str, message: str):
        self.stage = stage
        self.message = message
        super().__init__(message)


class ContextValidationError(ContextBuilderError):
    pass


class TokenCounterDependencyError(ContextBuilderError):
    pass
