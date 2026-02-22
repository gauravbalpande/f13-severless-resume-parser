import json
import os
import uuid
from decimal import Decimal

import boto3

dynamodb = boto3.resource("dynamodb")

CANDIDATE_TABLE_NAME = os.getenv("CANDIDATE_TABLE_NAME", "")
JOB_TABLE_NAME = os.getenv("JOB_TABLE_NAME", "")

candidate_table = dynamodb.Table(CANDIDATE_TABLE_NAME) if CANDIDATE_TABLE_NAME else None
job_table = dynamodb.Table(JOB_TABLE_NAME) if JOB_TABLE_NAME else None


def _decimal_default(obj):
    """Make DynamoDB Decimal values JSON-serializable."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")




def lambda_handler(event, context):
    """
    API Gateway proxy integration.

    Supported endpoints (all JSON):
    - GET    /jobs
    - POST   /jobs         (body: {title, description, required_skills: []})
    - GET    /candidates
    - GET    /candidates/{id}
    - GET    /candidates/{id}/report
    """
    if not candidate_table or not job_table:
        return _response(500, {"message": "Tables not configured"})

    path = event.get("path", "") or event.get("resource", "")
    http_method = event.get("httpMethod", "GET").upper()
    path_params = event.get("pathParameters") or {}

    try:
        if path.startswith("/jobs"):
            if http_method == "GET":
                return list_jobs()
            elif http_method == "POST":
                body = _parse_body(event.get("body"))
                return create_job(body)

        if http_method == "GET":
            parts = [p for p in path.split("/") if p]
            if parts and parts[-1] == "candidates" and len(parts) <= 2:
                return list_candidates()
            if "candidates" in parts and http_method == "GET":
                idx = parts.index("candidates")
                rest = parts[idx + 1:]
                if len(rest) == 1:
                    return get_candidate(rest[0])
                if len(rest) == 2 and rest[1] == "report":
                    return get_candidate_report(rest[0])

        return _response(404, {"message": "Not found"})
    except Exception as exc:  # pylint: disable=broad-except
        return _response(500, {"message": f"Internal error: {exc}"})


# Jobs


def list_jobs():
    resp = job_table.scan()
    items = resp.get("Items", [])
    return _response(200, {"items": items})


def create_job(body):
    title = body.get("title")
    description = body.get("description", "")
    required_skills = body.get("required_skills") or []

    if not title:
        return _response(400, {"message": "title is required"})

    job_id = str(uuid.uuid4())
    item = {
        "jobId": job_id,
        "title": title,
        "description": description,
        "required_skills": required_skills,
    }
    job_table.put_item(Item=item)
    return _response(201, item)


# Candidates


def list_candidates():
    resp = candidate_table.scan()
    items = resp.get("Items", [])
    # For the list view, we can return a subset of fields
    minimal = [
        {
            "candidateId": it.get("candidateId"),
            "name": it.get("name"),
            "email": it.get("email"),
            "total_experience_years": it.get("total_experience_years"),
            "skills": it.get("skills", []),
            "matches": it.get("matches", []),
        }
        for it in items
    ]
    return _response(200, {"items": minimal})


def get_candidate(candidate_id: str):
    resp = candidate_table.get_item(Key={"candidateId": candidate_id})
    item = resp.get("Item")
    if not item:
        return _response(404, {"message": "Candidate not found"})
    return _response(200, item)


def get_candidate_report(candidate_id: str):
    """
    Returns the full candidate object; frontend can treat it as a downloadable report.
    """
    resp = candidate_table.get_item(Key={"candidateId": candidate_id})
    item = resp.get("Item")
    if not item:
        return _response(404, {"message": "Candidate not found"})

    body = json.dumps(item, indent=2, default=_decimal_default)
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Content-Disposition": f'attachment; filename="candidate-{candidate_id}.json"',
            "Access-Control-Allow-Origin": "*",
        },
        "body": body,
    }


# Helpers


def _parse_body(body_str):
    if not body_str:
        return {}
    try:
        return json.loads(body_str)
    except json.JSONDecodeError:
        return {}


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=_decimal_default),
    }