import os
import boto3
from botocore.config import Config

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")


def get_r2_client():
    """Get a configured R2 (S3-compatible) client."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_file(file_content: bytes, key: str, content_type: str) -> str:
    """
    Upload a file to R2.
    
    Args:
        file_content: The file bytes
        key: The object key (path) in R2
        content_type: MIME type of the file
    
    Returns:
        The public URL of the uploaded file
    """
    client = get_r2_client()
    client.put_object(
        Bucket=R2_BUCKET_NAME,
        Key=key,
        Body=file_content,
        ContentType=content_type,
    )
    return f"{R2_PUBLIC_URL}/{key}"


def delete_file(key: str) -> bool:
    """
    Delete a file from R2.
    
    Args:
        key: The object key (path) in R2
    
    Returns:
        True if successful
    """
    client = get_r2_client()
    client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
    return True


def get_file(key: str) -> tuple[bytes, str]:
    """
    Get a file from R2.
    
    Args:
        key: The object key (path) in R2
    
    Returns:
        Tuple of (file_content, content_type)
    """
    client = get_r2_client()
    response = client.get_object(Bucket=R2_BUCKET_NAME, Key=key)
    return response["Body"].read(), response["ContentType"]
