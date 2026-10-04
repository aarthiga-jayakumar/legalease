"""AWS storage for LegalEase: uploaded PDFs go to S3, analysis results go to DynamoDB.

Configuration comes from environment variables so no names or keys live in the code:
    LEGALEASE_BUCKET   S3 bucket name
    LEGALEASE_TABLE    DynamoDB table name (default: legalease-results)
    AWS_REGION         region (default: ap-south-1)
Credentials come from the standard AWS chain (aws configure, env vars, or an EC2 IAM role).
"""
import os
from datetime import datetime, timezone

import boto3

DEFAULT_REGION = "ap-south-1"
DEFAULT_TABLE = "legalease-results"


class Storage:
    def __init__(self, bucket, table_name=DEFAULT_TABLE, region=DEFAULT_REGION, s3=None, dynamodb=None):
        if not bucket:
            raise RuntimeError("LEGALEASE_BUCKET is not set.")
        self.bucket = bucket
        self.s3 = s3 or boto3.client("s3", region_name=region)
        self.table = (dynamodb or boto3.resource("dynamodb", region_name=region)).Table(table_name)

    @classmethod
    def from_env(cls):
        return cls(
            bucket=os.environ.get("LEGALEASE_BUCKET"),
            table_name=os.environ.get("LEGALEASE_TABLE", DEFAULT_TABLE),
            region=os.environ.get("AWS_REGION", DEFAULT_REGION),
        )

    def save_upload(self, doc_id, data):
        """Store the original PDF in S3 and return its object key."""
        key = f"uploads/{doc_id}.pdf"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType="application/pdf")
        return key

    def save_result(self, doc_id, filename, question, report, s3_key):
        """Store the analysis result in DynamoDB and return the saved item."""
        item = {
            "id": doc_id,
            "filename": filename,
            "question": question or "",
            "report": report,
            "s3_key": s3_key,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.table.put_item(Item=item)
        return item

    def get_result(self, doc_id):
        """Return the saved item for an id, or None if it does not exist."""
        return self.table.get_item(Key={"id": doc_id}).get("Item")
