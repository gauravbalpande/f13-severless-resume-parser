import json
import os

import boto3

sqs = boto3.client("sqs")

QUEUE_URL = os.getenv("RESUME_QUEUE_URL", "")


def lambda_handler(event, context):
    """
    S3 event → enqueue message to SQS for downstream processing.

    Event shape (simplified):
    {
      "Records": [
        {
          "s3": {
            "bucket": {"name": "..."},
            "object": {"key": "..."}
          }
        }
      ]
    }
    """
    if not QUEUE_URL:
        raise RuntimeError("RESUME_QUEUE_URL is not configured")

    records = event.get("Records", [])
    for record in records:
        s3_info = record.get("s3", {})
        bucket = s3_info.get("bucket", {}).get("name")
        key = s3_info.get("object", {}).get("key")

        if not bucket or not key:
            continue

        message_body = json.dumps(
            {
                "bucket": bucket,
                "key": key,
            }
        )

        sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=message_body)

    return {"statusCode": 200, "body": json.dumps({"message": "Enqueued resumes for processing"})}

