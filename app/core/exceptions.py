class BaseAppException(Exception):
    """Base exception for application errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class InvalidDocumentError(BaseAppException):
    pass

class DuplicateDocumentError(BaseAppException):
    def __init__(self, message: str, document_id: str):
        self.document_id = document_id
        super().__init__(message)

class ObjectStorageError(BaseAppException):
    pass

class QueueError(BaseAppException):
    pass

class PDFExtractionError(BaseAppException):
    pass

class DatabaseError(BaseAppException):
    pass
