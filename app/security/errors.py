def safe_public_job_error(error_message: str | None) -> str | None:
    """Keep detailed worker diagnostics server-side and out of API payloads."""
    return "The background operation failed safely." if error_message else None
