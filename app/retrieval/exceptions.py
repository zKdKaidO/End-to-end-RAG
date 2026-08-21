class RetrievalError(Exception):
    def __init__(self, stage: str, message: str):
        self.stage = stage
        self.message = message
        super().__init__(message)


class RetrievalValidationError(RetrievalError):
    pass


class RetrievalDependencyError(RetrievalError):
    pass


class QueryInputTooLongError(RetrievalValidationError):
    def __init__(self, token_count: int, max_tokens: int):
        self.token_count = token_count
        self.max_tokens = max_tokens
        super().__init__(
            "QUERY_EMBEDDING",
            f"Query token count {token_count} exceeds model limit {max_tokens}; the query was not truncated",
        )
