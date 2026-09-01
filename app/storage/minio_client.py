import io
import urllib3
from minio import Minio
from minio.error import S3Error
from app.core.config import settings
from app.core.exceptions import ObjectStorageError
from app.core.logging import get_logger

logger = get_logger(__name__)

class MinioClient:
    def __init__(self):
        # Configure fail-fast HTTP client for synchronous API path
        http_client = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=2.0, read=5.0),
            retries=urllib3.Retry(
                total=2,
                backoff_factor=0.1,
                status_forcelist=[500, 502, 503, 504]
            )
        )
        
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            http_client=http_client
        )
        self.bucket = settings.MINIO_BUCKET

    def _generate_object_name(self, document_id: str) -> str:
        return f"{document_id}/original.pdf"

    def _generate_uri(self, object_name: str) -> str:
        return f"minio://{self.bucket}/{object_name}"

    def upload_pdf(self, document_id: str, file_data: bytes) -> str:
        """Uploads a PDF and returns the storage URI."""
        object_name = self._generate_object_name(document_id)
        data_stream = io.BytesIO(file_data)
        length = len(file_data)
        
        try:
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=object_name,
                data=data_stream,
                length=length,
                content_type="application/pdf"
            )
            logger.info("uploaded_pdf_to_storage", document_id=document_id, object_name=object_name)
            return self._generate_uri(object_name)
        except Exception as e:
            logger.error("minio_upload_failed", document_id=document_id, error=str(e))
            raise ObjectStorageError(f"Failed to upload document {document_id}") from e

    def download_pdf(self, document_id: str) -> bytes:
        """Downloads a PDF and returns its bytes."""
        object_name = self._generate_object_name(document_id)
        
        try:
            response = self.client.get_object(self.bucket, object_name)
            try:
                data = response.read()
                return data
            finally:
                response.close()
                response.release_conn()
        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.error("minio_download_not_found", document_id=document_id, object_name=object_name)
                raise ObjectStorageError(f"Document {document_id} not found in storage") from e
            logger.error("minio_download_failed", document_id=document_id, error=str(e))
            raise ObjectStorageError(f"Failed to download document {document_id}") from e
        except Exception as e:
            logger.error("minio_download_error", document_id=document_id, error=str(e))
            raise ObjectStorageError(f"Failed to download document {document_id}") from e

    def exists(self, document_id: str) -> bool:
        object_name = self._generate_object_name(document_id)
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise ObjectStorageError(f"Failed to check existence for {document_id}") from e
        except Exception as e:
            raise ObjectStorageError(f"Failed to check existence for {document_id}") from e

    def delete(self, document_id: str) -> None:
        object_name = self._generate_object_name(document_id)
        try:
            self.client.remove_object(self.bucket, object_name)
            logger.info("deleted_pdf_from_storage", document_id=document_id, object_name=object_name)
        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.info("pdf_already_absent_from_storage", document_id=document_id, object_name=object_name)
                return
            logger.error("minio_delete_failed", document_id=document_id, error=str(e))
            raise ObjectStorageError(f"Failed to delete document {document_id}") from e
        except Exception as e:
            logger.error("minio_delete_failed", document_id=document_id, error=str(e))
            raise ObjectStorageError(f"Failed to delete document {document_id}") from e

    def check_health(self) -> bool:
        try:
            return self.client.bucket_exists(self.bucket)
        except Exception as e:
            logger.error("minio_health_check_failed", error=str(e))
            return False

minio_client = MinioClient()
