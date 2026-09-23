"""
Pydantic models and shared payload schemas for Reach API endpoints.
"""

from typing import List, Optional
from pydantic import BaseModel


class UpdateEmailPayload(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    generated_subject: Optional[str] = None
    generated_body: Optional[str] = None


class GenerateBatchPayload(BaseModel):
    post_ids: List[str]
    force: bool = False


class SendBatchPayload(BaseModel):
    post_ids: List[str]


class BatchPostActionPayload(BaseModel):
    post_ids: List[str]
    reason: Optional[str] = None


class RejectPostPayload(BaseModel):
    reason: Optional[str] = None


class SpamPostPayload(BaseModel):
    reason: Optional[str] = "Scam"


class ManualPostPayload(BaseModel):
    author_name: Optional[str] = None
    company: Optional[str] = None
    author_headline: Optional[str] = None
    title: Optional[str] = None
    full_text: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    contact_emails: Optional[List[str]] = None
    post_url: Optional[str] = None
    location: Optional[str] = None


class SettingsPayload(BaseModel):
    resume_path: Optional[str] = None
    search_query: Optional[str] = None
    search_location: Optional[str] = None
    chatgpt_url: Optional[str] = None
    pacing_min_seconds: Optional[float] = None
    pacing_max_seconds: Optional[float] = None
    headless_mode: Optional[bool] = None
    headless: Optional[bool] = None


class HeadlessTogglePayload(BaseModel):
    headless: bool


class ScrapePayload(BaseModel):
    source: Optional[str] = "linkedin"
    location: Optional[str] = None
    search_query: Optional[str] = None
    time_filter: Optional[str] = "24h"


MAJOR_JOB_HUBS = [
    "San Francisco", "Seattle", "New York", "Boston", "Austin", "Los Angeles",
    "Toronto", "Vancouver", "Montreal",
    "London", "Dublin", "Amsterdam", "Berlin", "Paris", "Stockholm", "Copenhagen", "Zurich", "Munich",
    "Singapore", "Tokyo", "Seoul", "Beijing", "Shanghai", "Shenzhen", "Hong Kong",
    "Bengaluru", "Hyderabad", "Pune", "Chennai", "Mumbai", "Delhi", "Kochi",
    "Dubai", "Abu Dhabi", "Riyadh", "Doha", "Manama", "Kuwait City", "Muscat", "Tel Aviv",
    "Sydney", "Melbourne", "Auckland",
    "São Paulo", "Mexico City", "Buenos Aires",
    "Cape Town", "Johannesburg", "Nairobi", "Remote"
]

DEFAULT_OPPORTUNITY_SUBJECT = "Full-Stack Software Engineer – Job Opportunities"
DEFAULT_OPPORTUNITY_BODY = """Hi,

I’m Mohammed Rinshad, a Full-Stack Software Engineer with 3+ years of experience in web and enterprise application development.

My experience includes React, Next.js, Node.js, TypeScript, .NET Core, REST APIs, PostgreSQL, SQL Server, Azure, GCP, CI/CD, authentication, RBAC, and database design. I’ve worked on ERP, accounting, education, and enterprise applications, including both frontend and backend development.

I’m currently looking for opportunities in Frontend, Backend, Full-Stack, DevOps, or Cloud Engineering. I’m open to relocating for the right opportunity and am also interested in remote roles.

I’ve attached my resume for reference. If there are any current or upcoming openings that match my background, I’d be grateful to be considered.

Regards,
Mohammed Rinshad P
+91 98956 12423
rinshadmorayur09@gmail.com
LinkedIn: linkedin.com/in/mrinshad
GitHub: github.com/mrinshad"""


class DirectOutreachPayload(BaseModel):
    recipient_email: str
    company_name: Optional[str] = None
    location: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    mode: Optional[str] = "send"
