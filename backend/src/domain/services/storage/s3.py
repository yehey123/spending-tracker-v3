import asyncio

from src.domain.services.storage.base import StorageBackend, StorageError


class S3Backend(StorageBackend):

    def __init__(
        self,
        bucket: str,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region_name: str = "us-east-1",
    ) -> None:
        self._bucket = bucket
        self._key_id = aws_access_key_id
        self._secret = aws_secret_access_key
        self._region = region_name

    def _client(self):
        import boto3  # lazy import — SDK not required at module load time
        return boto3.client(
            "s3",
            aws_access_key_id=self._key_id,
            aws_secret_access_key=self._secret,
            region_name=self._region,
        )

    async def save(self, key: str, content: bytes) -> str:
        client = self._client()
        try:
            await asyncio.to_thread(
                client.put_object, Bucket=self._bucket, Key=key, Body=content
            )
        except Exception as e:
            # boto3 ClientError and any unexpected error
            raise StorageError(f"S3 write failed for key {key!r}: {e}") from e
        return key

    async def delete(self, key: str) -> None:
        client = self._client()
        try:
            await asyncio.to_thread(
                client.delete_object, Bucket=self._bucket, Key=key
            )
        except Exception as e:
            # boto3 raises ClientError for 404 (NoSuchKey) — treat as silent no-op
            try:
                import botocore.exceptions
                if isinstance(e, botocore.exceptions.ClientError):
                    code = e.response.get("Error", {}).get("Code", "")
                    if code in ("NoSuchKey", "404"):
                        return
            except ImportError:
                pass
            raise StorageError(f"S3 delete failed for key {key!r}: {e}") from e
