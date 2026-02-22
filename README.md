## AI-Powered Resume Parser & Job Matcher

This project is a **reference implementation** of a backend system that:

- **Ingests resumes (PDF) into S3**
- **Parses them with AWS Textract + simple NLP in Lambda**
- **Stores job descriptions and parsed candidates in DynamoDB**
- **Matches candidates to jobs using Jaccard similarity on skills**
- **Exposes an HTTP API for a simple recruiter dashboard**
- **Provides a static HTML/JS dashboard** to browse candidates and download reports

### High-Level Architecture

- **S3 bucket**: Stores uploaded PDF resumes.
- **S3 → SQS → Lambda pipeline**:
  - S3 upload event triggers an **enqueue Lambda**.
  - Enqueue Lambda sends a message to an **SQS queue**.
  - An SQS-triggered **resume-processor Lambda**:
    - Calls **Textract** to extract text from the PDF.
    - Runs lightweight NLP to extract:
      - Skills (keywords)
      - Job titles
      - Total experience (approx. years)
    - Stores a **candidate profile** and precomputed **job matches** into DynamoDB.
- **DynamoDB**:
  - `Jobs` table: stores job descriptions and required skills.
  - `Candidates` table: stores parsed resume data and match scores.
- **API Gateway + Lambda**:
  - Exposes simple REST endpoints to list jobs, candidates, and matches, and to download candidate reports.
- **Static dashboard** (`frontend/`):
  - HTML/JS app that talks to the API.
  - Lets recruiters see parsed candidates, their extracted skills, and best-matching jobs.

### Key Directories

- `backend/`
  - AWS SAM template and Lambda source code for:
    - S3 → SQS → Lambda resume-processing pipeline.
    - HTTP API for recruiter dashboard.
- `frontend/`
  - Simple HTML/CSS/JS dashboard that calls the backend API.
- `sample_data/`
  - Example of parsed resume output for quick understanding.

### Documentation

- `DEPLOYMENT.md` – **Step-by-step guide** to deploy with AWS SAM and host the frontend.
- `PROJECT_OVERVIEW_SIMPLE.md` – **Non-technical explanation** of the project in easy terms.

### Tech Stack

- **Backend**: AWS SAM, Lambda (Python), S3, SQS, Textract, DynamoDB, API Gateway, IAM.
- **Frontend**: Static HTML, CSS, and vanilla JavaScript.

You can treat this as a starting point and adapt it to your own AWS account, security policies, and scaling needs.

