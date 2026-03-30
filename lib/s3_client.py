"""AWS S3 client for call recording storage."""

import os
import boto3
from botocore.config import Config


_client = None


def get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            config=Config(signature_version="s3v4"),
        )
    return _client


BUCKET = os.environ.get("S3_CALL_BUCKET", "revryze-call-recordings")


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    return get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )


def upload_file(local_path: str, key: str):
    get_client().upload_file(local_path, BUCKET, key)


def list_recordings(prefix: str = "") -> list[str]:
    resp = get_client().list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    return [obj["Key"] for obj in resp.get("Contents", [])]
