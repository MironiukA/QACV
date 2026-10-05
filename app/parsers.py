import ipaddress
import socket
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import pymupdf
from bs4 import BeautifulSoup
from docx import Document
from fastapi import HTTPException, UploadFile, status


MAX_RESUME_SIZE = 10 * 1024 * 1024
STORAGE_DIR = Path("storage/resumes")
SUPPORTED_EXTENSIONS = {".pdf", ".docx"}

KNOWN_REQUIREMENTS = {
    "python": ("Python", "skill", "must_have"),
    "sql": ("SQL", "skill", "must_have"),
    "postgresql": ("PostgreSQL", "skill", "nice_to_have"),
    "api": ("API testing", "skill", "must_have"),
    "postman": ("Postman", "skill", "nice_to_have"),
    "pytest": ("pytest", "skill", "nice_to_have"),
    "selenium": ("Selenium", "skill", "nice_to_have"),
    "playwright": ("Playwright", "skill", "nice_to_have"),
    "docker": ("Docker", "skill", "nice_to_have"),
    "ci/cd": ("CI/CD", "skill", "nice_to_have"),
    "git": ("Git", "skill", "nice_to_have"),
    "linux": ("Linux", "skill", "nice_to_have"),
}


async def save_and_extract_resume(file: UploadFile) -> tuple[str, str]:
    filename = file.filename or "resume"
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF and DOCX resumes are supported",
        )

    content = await file.read()
    if not content or len(content) > MAX_RESUME_SIZE:
        raise HTTPException(status_code=413, detail="Resume must be between 1 byte and 10 MB")

    try:
        text = _extract_resume_text(content, extension)
    except Exception as error:
        raise HTTPException(status_code=422, detail="Could not read the resume file") from error

    if not text.strip():
        raise HTTPException(status_code=422, detail="The resume contains no readable text")

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4()}{extension}"
    path = STORAGE_DIR / stored_name
    path.write_bytes(content)
    return str(path), text.strip()


def _extract_resume_text(content: bytes, extension: str) -> str:
    if extension == ".pdf":
        document = pymupdf.open(stream=content, filetype="pdf")
        try:
            return "\n".join(page.get_text() for page in document)
        finally:
            document.close()

    document = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def fetch_vacancy_page(source_url: str) -> tuple[str, str]:
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="A public HTTP or HTTPS URL is required")

    _ensure_public_host(parsed.hostname)
    try:
        with httpx.Client(timeout=10.0, follow_redirects=False) as client:
            response = client.get(source_url, headers={"User-Agent": "QACV vacancy parser/0.1"})
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=422, detail="Could not download the vacancy URL") from error

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else parsed.hostname
    text = soup.get_text("\n", strip=True)
    if not text:
        raise HTTPException(status_code=422, detail="The vacancy page contains no readable text")
    return title[:150], text[:100_000]


def extract_known_requirements(vacancy_text: str) -> list[dict[str, str]]:
    text = vacancy_text.lower()
    requirements = []
    for trigger, (name, category, priority) in KNOWN_REQUIREMENTS.items():
        start = text.find(trigger)
        if start >= 0:
            requirements.append(
                {
                    "name": name,
                    "category": category,
                    "priority": priority,
                    "source_text": vacancy_text[start : start + len(trigger)],
                }
            )
    return requirements


def _ensure_public_host(hostname: str) -> None:
    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise HTTPException(status_code=422, detail="Could not resolve vacancy host") from error

    for _, _, _, _, address in addresses:
        if not ipaddress.ip_address(address[0]).is_global:
            raise HTTPException(status_code=422, detail="Private vacancy URLs are not allowed")
