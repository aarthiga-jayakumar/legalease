"""Create the S3 bucket and DynamoDB table LegalEase needs. Safe to run more than once.

Usage:
    python scripts/setup_aws.py
Prints the environment variables to set afterwards.
"""
import os

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "ap-south-1")
TABLE = os.environ.get("LEGALEASE_TABLE", "legalease-results")


def main():
    account = boto3.client("sts").get_caller_identity()["Account"]
    bucket = os.environ.get("LEGALEASE_BUCKET", f"legalease-{account}-{REGION}")

    s3 = boto3.client("s3", region_name=REGION)
    try:
        s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": REGION})
        print(f"Created bucket {bucket}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("BucketAlreadyOwnedByYou",):
            print(f"Bucket {bucket} already exists")
        else:
            raise
    s3.put_public_access_block(
        Bucket=bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )

    ddb = boto3.client("dynamodb", region_name=REGION)
    try:
        ddb.create_table(
            TableName=TABLE,
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb.get_waiter("table_exists").wait(TableName=TABLE)
        print(f"Created table {TABLE}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceInUseException":
            print(f"Table {TABLE} already exists")
        else:
            raise

    print("\nNow set these before starting the API:")
    print(f"  export LEGALEASE_BUCKET={bucket}")
    print(f"  export LEGALEASE_TABLE={TABLE}")
    print(f"  export AWS_REGION={REGION}")
    print("  export GROQ_API_KEY=your_key_here")


if __name__ == "__main__":
    main()
