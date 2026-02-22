import json
import math
import os
import re
import uuid
from collections import Counter
from typing import Dict, List, Tuple

import boto3

textract = boto3.client("textract")
dynamodb = boto3.resource("dynamodb")

RESUME_BUCKET_NAME = os.getenv("RESUME_BUCKET_NAME", "")
CANDIDATE_TABLE_NAME = os.getenv("CANDIDATE_TABLE_NAME", "")
JOB_TABLE_NAME = os.getenv("JOB_TABLE_NAME", "")

candidate_table = dynamodb.Table(CANDIDATE_TABLE_NAME) if CANDIDATE_TABLE_NAME else None
job_table = dynamodb.Table(JOB_TABLE_NAME) if JOB_TABLE_NAME else None

# Simple keyword list for demo; extend or load from config as needed.
SKILL_KEYWORDS = {
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "node",
    "node.js",
    "aws",
    "lambda",
    "dynamodb",
    "s3",
    "kubernetes",
    "docker",
    "sql",
    "nosql",
    "postgres",
    "mysql",
    "mongodb",
    "terraform",
    "jenkins",
    "git",
    "rest",
    "api",
    "machine learning",
    "data science",
    "pandas",
    "numpy",
}


def lambda_handler(event, context):
    """
    SQS event → download resume from S3 → Textract → parse → match → store.

    Event (simplified):
    {
      "Records": [
        {
          "body": "{\"bucket\": \"...\", \"key\": \"...\"}"
        }
      ]
    }
    """
    if not candidate_table or not job_table:
        raise RuntimeError("DynamoDB tables are not configured")

    for record in event.get("Records", []):
        body = json.loads(record.get("body", "{}"))
        bucket = body.get("bucket") or RESUME_BUCKET_NAME
        key = body.get("key")

        if not bucket or not key:
            continue

        full_text = extract_text_with_textract(bucket, key)

        candidate_profile = parse_candidate_profile(full_text)

        # Assign a deterministic-ish ID (could also hash S3 key)
        candidate_id = str(uuid.uuid4())
        candidate_profile["candidateId"] = candidate_id
        candidate_profile["sourceObjectKey"] = key

        # Compute matches versus all jobs
        jobs = list_all_jobs()
        matches = compute_matches(candidate_profile, jobs)
        candidate_profile["matches"] = matches

        # Persist candidate
        candidate_table.put_item(Item=candidate_profile)

    return {"statusCode": 200, "body": json.dumps({"message": "Processed resumes"})}


def extract_text_with_textract(bucket: str, key: str) -> str:
    """
    Use Textract to extract raw text from a PDF in S3.
    For simplicity, uses DetectDocumentText which is synchronous.
    """
    response = textract.detect_document_text(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )

    lines: List[str] = []
    for block in response.get("Blocks", []):
        if block.get("BlockType") == "LINE":
            text = block.get("Text")
            if text:
                lines.append(text)

    return "\n".join(lines)


def parse_candidate_profile(text: str) -> Dict:
    """
    Very simple NLP to extract:
    - name (first non-empty line, heuristic)
    - email
    - total experience (approx years)
    - skills (overlapping with SKILL_KEYWORDS)
    - titles (lines with known words like 'engineer', 'developer', 'manager', etc.)
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    lower_text = text.lower()

    name = lines[0] if lines else "Unknown"
    email = extract_email(text)
    experience_years = extract_experience_years(lower_text)
    skills = extract_skills(lower_text)
    titles = extract_titles(lower_text)

    return {
        "name": name,
        "email": email,
        "total_experience_years": experience_years,
        "skills": sorted(list(skills)),
        "titles": sorted(list(titles)),
        "raw_text": text[:5000],  # store a truncated version to keep items small
    }


def extract_email(text: str) -> str:
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else ""


def extract_experience_years(lower_text: str) -> float:
    """
    Look for patterns like 'X years' or 'X+ years'.
    Returns max number found as an approximation.
    """
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*years?", lower_text)
    years = [float(m) for m in matches]
    return max(years) if years else 0.0


def extract_skills(lower_text: str) -> set:
    found = set()
    for skill in SKILL_KEYWORDS:
        if skill in lower_text:
            found.add(skill)
    return found


def extract_titles(lower_text: str) -> set:
    # Very simple heuristic
    title_keywords = ["engineer", "developer", "manager", "lead", "architect", "analyst"]
    titles = set()
    for line in lower_text.splitlines():
        if any(word in line for word in title_keywords):
            titles.add(line.strip())
    return titles


def list_all_jobs() -> List[Dict]:
    response = job_table.scan()
    items = response.get("Items", [])
    # If there are more than 1MB of data, you would paginate using LastEvaluatedKey.
    return items


def compute_matches(candidate: Dict, jobs: List[Dict]) -> List[Dict]:
    """
    Compute similarity between candidate skills and job required_skills.
    Uses:
    - Jaccard similarity on skill sets as primary score.
    """
    candidate_skills = set(s.lower() for s in candidate.get("skills", []))
    results: List[Tuple[str, float]] = []

    for job in jobs:
        job_id = job.get("jobId")
        required_skills = set(
            s.lower() for s in job.get("required_skills", []) if isinstance(s, str)
        )
        if not job_id or not required_skills:
            continue

        score = jaccard_similarity(candidate_skills, required_skills)
        if score > 0:
            results.append((job_id, score))

    # sort best first and keep top 10
    results.sort(key=lambda x: x[1], reverse=True)
    top = results[:10]
    return [{"jobId": jid, "score": round(score, 3)} for jid, score in top]


def jaccard_similarity(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0

