"""
extractor.py

Step 8 Part A:
Fetches and cleans HTML page text for future extraction.

This does not extract presidents, board chairs, emails, or names yet.
It only prepares clean page text from extraction-ready page records.
"""

from datetime import datetime
from urllib.parse import urlparse

import re
import requests
from bs4 import BeautifulSoup


REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_TEXT_LIMIT = 12000

CATEGORY_TEXT_LIMITS = {
    "directory": 50000,
    "leadership": 20000,
    "board": 20000,
    "strategic_plan": 12000,
}


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


SKIPPED_FILE_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".zip",
    ".mp3",
    ".mp4",
    ".ics",
)


def get_retrieved_at() -> str:
    """
    Returns a consistent timestamp for fetched pages.
    """
    return datetime.now().isoformat(timespec="seconds")


def is_probably_file_url(url: str) -> bool:
    """
    Returns True if the URL appears to point to a file instead of an HTML page.
    """
    if not url:
        return False

    parsed = urlparse(url)
    path = parsed.path.lower()

    return path.endswith(SKIPPED_FILE_EXTENSIONS)


def clean_whitespace(text: str) -> str:
    """
    Normalizes whitespace while preserving readable text.
    """
    if not text:
        return ""

    lines = []

    for line in text.splitlines():
        cleaned_line = " ".join(line.split())

        if cleaned_line:
            lines.append(cleaned_line)

    return "\n".join(lines)


def extract_page_title(soup: BeautifulSoup) -> str:
    """
    Extracts a readable title from the page.
    """
    if soup.title and soup.title.string:
        return clean_whitespace(soup.title.string)

    h1 = soup.find("h1")

    if h1:
        return clean_whitespace(h1.get_text(" ", strip=True))

    return ""


def remove_noise_elements(soup: BeautifulSoup):
    """
    Removes elements that usually create noise in extraction text.
    """
    noisy_tags = [
        "script",
        "style",
        "noscript",
        "svg",
        "iframe",
        "form",
        "nav",
        "footer",
        "header",
    ]

    for tag_name in noisy_tags:
        for tag in soup.find_all(tag_name):
            tag.decompose()


def extract_main_text(soup: BeautifulSoup, category: str = "") -> str:
    """
    Extracts readable page text.

    Preference order:
    1. main element
    2. article element
    3. body element
    4. full soup text
    """
    remove_noise_elements(soup)

    main = soup.find("main")

    if main:
        text = main.get_text("\n", strip=True)
    else:
        article = soup.find("article")

        if article:
            text = article.get_text("\n", strip=True)
        elif soup.body:
            text = soup.body.get_text("\n", strip=True)
        else:
            text = soup.get_text("\n", strip=True)

    text = clean_whitespace(text)

    text_limit = CATEGORY_TEXT_LIMITS.get(category, DEFAULT_TEXT_LIMIT)

    if len(text) > text_limit:
        text = text[:text_limit]

    return text


def fetch_html_page_text(page_record: dict) -> dict:
    """
    Fetches and cleans text from one extraction-ready page record.

    Expected input:
        {
            "organization": "...",
            "category": "...",
            "page_title": "...",
            "url": "...",
            "needs_review": False,
        }

    Returns:
        {
            "organization": "...",
            "category": "...",
            "source_page_title": "...",
            "url": "...",
            "status": "fetched" | "skipped" | "error",
            "status_code": 200,
            "content_type": "text/html",
            "title": "...",
            "text": "...",
            "text_length": 1234,
            "retrieved_at": "...",
            "error": "",
        }
    """
    url = page_record.get("url", "")
    organization = page_record.get("organization", "")
    category = page_record.get("category", "")
    source_page_title = page_record.get("page_title", "")

    result = {
        "organization": organization,
        "category": category,
        "source_page_title": source_page_title,
        "url": url,
        "status": "",
        "status_code": None,
        "content_type": "",
        "title": "",
        "text": "",
        "text_length": 0,
        "retrieved_at": get_retrieved_at(),
        "error": "",
    }

    if not url:
        result["status"] = "skipped"
        result["error"] = "empty URL"
        return result

    if is_probably_file_url(url):
        result["status"] = "skipped"
        result["error"] = "file URL skipped for now"
        return result

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )

        result["status_code"] = response.status_code
        result["content_type"] = response.headers.get("content-type", "")

        if response.status_code >= 400:
            result["status"] = "error"
            result["error"] = f"HTTP error {response.status_code}"
            return result

        if "text/html" not in result["content_type"].lower():
            result["status"] = "skipped"
            result["error"] = "non-HTML content skipped for now"
            return result

        soup = BeautifulSoup(response.text, "lxml")

        title = extract_page_title(soup)
        text = extract_main_text(soup, category=category)

        result["status"] = "fetched"
        result["title"] = title
        result["text"] = text
        result["text_length"] = len(text)

        return result

    except requests.RequestException as e:
        result["status"] = "error"
        result["error"] = str(e)
        return result

    except Exception as e:
        result["status"] = "error"
        result["error"] = f"unexpected extraction fetch error: {e}"
        return result


def fetch_html_page_texts(
    page_records: list[dict],
    limit: int | None = None,
    skip_review_pages: bool = True,
    max_attempts: int | None = None,
) -> list[dict]:
    """
    Fetches clean text for multiple extraction-ready page records.

    By default:
    - review pages are skipped
    - errors and skipped files are still shown for visibility
    - only successfully fetched HTML pages count toward the requested limit
    """
    results = []
    attempts = 0
    fetched_success_count = 0

    pages_to_fetch = []

    for page in page_records:
        if skip_review_pages and page.get("needs_review"):
            continue

        pages_to_fetch.append(page)

    if max_attempts is None:
        max_attempts = len(pages_to_fetch)

    for page in pages_to_fetch:
        if attempts >= max_attempts:
            break

        attempts += 1

        fetched = fetch_html_page_text(page)
        results.append(fetched)

        if fetched.get("status") == "fetched":
            fetched_success_count += 1

        if limit is not None and fetched_success_count >= limit:
            break

    return results
def extract_emails_from_text(text: str) -> list[str]:
    """
    Extracts email addresses from cleaned page text.
    """
    if not text:
        return []

    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"

    emails = re.findall(email_pattern, text)

    cleaned_emails = []

    for email in emails:
        cleaned = email.strip().strip(".,;:()[]{}<>")

        if cleaned and cleaned not in cleaned_emails:
            cleaned_emails.append(cleaned)

    return cleaned_emails


def extract_phones_from_text(text: str) -> list[str]:
    """
    Extracts common U.S. phone number formats from cleaned page text.
    """
    if not text:
        return []

    phone_pattern = r"""
        (?:
            (?:\+1[\s.-]?)?
            (?:\(?\d{3}\)?[\s.-]?)
            \d{3}[\s.-]?\d{4}
            (?:\s*(?:x|ext|extension)\s*\d{1,6})?
        )
    """

    matches = re.findall(
        phone_pattern,
        text,
        flags=re.IGNORECASE | re.VERBOSE,
    )

    cleaned_phones = []

    for phone in matches:
        cleaned = " ".join(phone.split())
        cleaned = cleaned.strip().strip(".,;:")

        if cleaned and cleaned not in cleaned_phones:
            cleaned_phones.append(cleaned)

    return cleaned_phones


def extract_basic_contacts_from_fetched_page(fetched_page: dict) -> dict:
    """
    Extracts basic contact signals from one fetched HTML page.

    This does not classify contacts by role yet.
    It only extracts emails and phone numbers.
    """
    text = fetched_page.get("text", "")

    emails = extract_emails_from_text(text)
    phones = extract_phones_from_text(text)

    return {
        "organization": fetched_page.get("organization", ""),
        "category": fetched_page.get("category", ""),
        "source_page_title": fetched_page.get("source_page_title", ""),
        "url": fetched_page.get("url", ""),
        "fetch_status": fetched_page.get("status", ""),
        "status_code": fetched_page.get("status_code", ""),
        "fetched_title": fetched_page.get("title", ""),
        "emails": emails,
        "phones": phones,
        "email_count": len(emails),
        "phone_count": len(phones),
        "text_length": fetched_page.get("text_length", 0),
    }


def extract_basic_contacts_from_fetched_pages(
    fetched_pages: list[dict],
) -> list[dict]:
    """
    Extracts basic contact signals from multiple fetched pages.
    """
    contact_results = []

    for fetched_page in fetched_pages:
        if fetched_page.get("status") != "fetched":
            continue

        contact_result = extract_basic_contacts_from_fetched_page(fetched_page)
        contact_results.append(contact_result)

    return contact_results


def summarize_basic_contact_extraction(contact_results: list[dict]) -> dict:
    """
    Summarizes basic contact extraction results.
    """
    summary = {
        "pages_processed": len(contact_results),
        "pages_with_emails": 0,
        "pages_with_phones": 0,
        "total_emails": 0,
        "total_phones": 0,
    }

    for result in contact_results:
        email_count = result.get("email_count", 0)
        phone_count = result.get("phone_count", 0)

        summary["total_emails"] += email_count
        summary["total_phones"] += phone_count

        if email_count > 0:
            summary["pages_with_emails"] += 1

        if phone_count > 0:
            summary["pages_with_phones"] += 1

    return summary

def normalize_directory_name(name: str) -> str:
    """
    Normalizes names from formats like:
        Last, First
    into:
        First Last

    If the name is already normal, it returns it mostly unchanged.
    """
    if not name:
        return ""

    name = " ".join(name.split()).strip()

    if "," in name:
        parts = [part.strip() for part in name.split(",", 1)]

        if len(parts) == 2:
            last_name = parts[0]
            first_name = parts[1]

            if first_name and last_name:
                return f"{first_name} {last_name}"

    return name


def looks_like_directory_label(line: str) -> bool:
    """
    Filters out common labels/header text from directory rows.
    """
    if not line:
        return True

    normalized = line.strip().lower()

    labels = {
        "name",
        "title",
        "department",
        "phone",
        "email",
        "link",
        "campus directory",
        "faculty/staff directory",
        "employee directory",
    }

    return normalized in labels


def extract_structured_directory_contacts_from_text(
    text: str,
) -> list[dict]:
    """
    Turns directory text into structured contact records.

    Supports common layouts including:

    Layout 1:
        Name
        Title
        Department
        Optional Phone
        Email

    Layout 2:
        First Name
        Last Name
        Title
        Department
        Office
        Email
        Phone

    A contact block ends when an email is found.
    """
    if not text:
        return []

    lines = []

    for line in text.splitlines():
        cleaned = " ".join(line.split()).strip()

        if cleaned:
            lines.append(cleaned)

    contacts = []
    seen_emails = set()
    current_block = []

    for line in lines:
        emails = extract_emails_from_text(line)

        if emails:
            email = emails[0]

            if email.lower() in seen_emails:
                current_block = []
                continue

            seen_emails.add(email.lower())

            useful_lines = []

            for block_line in current_block:
                if looks_like_directory_label(block_line):
                    continue

                if extract_emails_from_text(block_line):
                    continue

                useful_lines.append(block_line)

            phone = ""
            non_phone_lines = []

            for block_line in useful_lines:
                phones = extract_phones_from_text(block_line)

                if phones and not phone:
                    phone = phones[0]
                elif not phones:
                    non_phone_lines.append(block_line)

            raw_name = ""
            title = ""
            department = ""

            # Cascadia-style layout:
            # First Name, Last Name, Title, Department, Office
            if len(non_phone_lines) >= 5:
                first_name = non_phone_lines[-5]
                last_name = non_phone_lines[-4]
                possible_title = non_phone_lines[-3]
                possible_department = non_phone_lines[-2]
                possible_office = non_phone_lines[-1]

                office_lower = possible_office.lower()

                looks_like_office = (
                    "office" in office_lower
                    or "no office" in office_lower
                    or any(character.isdigit() for character in possible_office)
                )

                if looks_like_office:
                    raw_name = f"{first_name} {last_name}"
                    title = possible_title
                    department = possible_department

            # Most common layout:
            # Name, Title, Department
            if not raw_name and len(non_phone_lines) >= 3:
                raw_name = non_phone_lines[-3]
                title = non_phone_lines[-2]
                department = non_phone_lines[-1]

            elif not raw_name and len(non_phone_lines) == 2:
                raw_name = non_phone_lines[-2]
                title = non_phone_lines[-1]

            elif not raw_name and len(non_phone_lines) == 1:
                raw_name = non_phone_lines[-1]

            if looks_like_directory_label(raw_name):
                raw_name = ""

            if looks_like_directory_label(title):
                title = ""

            if looks_like_directory_label(department):
                department = ""

            name = normalize_directory_name(raw_name)

            contacts.append(
                {
                    "name": name,
                    "title": title,
                    "department": department,
                    "phone": phone,
                    "email": email,
                }
            )

            current_block = []

        else:
            current_block.append(line)

    return contacts
def _looks_like_directory_person_name(name: str) -> bool:
    """
    Rejects office names, role labels, headings, and other non-person values
    that were incorrectly parsed as directory contact names.
    """
    if not name:
        return False

    value = " ".join(name.strip().split())
    lower_value = value.lower()

    if len(value) < 4 or len(value) > 80:
        return False

    blocked_exact_values = {
        "president",
        "executive assistant",
        "president's office",
        "presidents office",
        "office of the president",
        "email president's office",
        "email presidents office",
        "vice president",
        "chancellor",
        "administration",
        "leadership",
        "directory",
        "contact us",
    }

    if lower_value in blocked_exact_values:
        return False

    blocked_phrases = [
        "office of",
        "president's office",
        "presidents office",
        "email ",
        "department",
        "division",
        "services",
        "administration",
        "directory",
        "contact",
        "main office",
        "switchboard",
    ]

    if any(phrase in lower_value for phrase in blocked_phrases):
        return False

    parts = value.replace(",", " ").split()

    if len(parts) < 2 or len(parts) > 6:
        return False

    if not any(character.isalpha() for character in value):
        return False

    return True

def extract_structured_directory_contacts_from_fetched_page(
    fetched_page: dict,
) -> list[dict]:
    """
    Extracts structured directory contacts from one fetched page and rejects
    records whose parsed name is clearly an office, role, or page heading.
    """
    if fetched_page.get("status") != "fetched":
        return []

    if fetched_page.get("category") != "directory":
        return []

    text = fetched_page.get("text", "")

    contacts = extract_structured_directory_contacts_from_text(text)

    enriched_contacts = []

    for contact in contacts:
        name = contact.get("name", "").strip()

        if not _looks_like_directory_person_name(name):
            continue

        enriched_contact = {
            "organization": fetched_page.get("organization", ""),
            "source_page_title": fetched_page.get(
                "source_page_title",
                "",
            ),
            "fetched_title": fetched_page.get("title", ""),
            "source_url": fetched_page.get("url", ""),
            "name": name,
            "title": contact.get("title", ""),
            "department": contact.get("department", ""),
            "phone": contact.get("phone", ""),
            "email": contact.get("email", ""),
            "source_type": "directory_page",
        }

        enriched_contacts.append(enriched_contact)

    return enriched_contacts

def extract_structured_directory_contacts_from_fetched_pages(
    fetched_pages: list[dict],
) -> list[dict]:
    """
    Extracts structured directory contacts from multiple fetched pages.
    """
    all_contacts = []

    for fetched_page in fetched_pages:
        contacts = extract_structured_directory_contacts_from_fetched_page(
            fetched_page
        )

        all_contacts.extend(contacts)

    return all_contacts


def summarize_structured_directory_contacts(contacts: list[dict]) -> dict:
    """
    Summarizes structured directory contact extraction.
    """
    summary = {
        "total_contacts": len(contacts),
        "contacts_with_name": 0,
        "contacts_with_title": 0,
        "contacts_with_department": 0,
        "contacts_with_phone": 0,
        "contacts_with_email": 0,
    }

    for contact in contacts:
        if contact.get("name"):
            summary["contacts_with_name"] += 1

        if contact.get("title"):
            summary["contacts_with_title"] += 1

        if contact.get("department"):
            summary["contacts_with_department"] += 1

        if contact.get("phone"):
            summary["contacts_with_phone"] += 1

        if contact.get("email"):
            summary["contacts_with_email"] += 1

    return summary

ROLE_TARGET_KEYWORDS = {
    "president_chancellor": [
        "president",
        "chancellor",
        "college president",
        "interim president",
        "acting president",
        "office of the president",
    ],
    "executive_assistant": [
        "exec asst to the president",
        "executive assistant to the president",
        "executive assistant",
        "assistant to the president",
        "assistant to president",
        "administrative assistant to the president",
        "admin assistant to the president",
        "president's assistant",
        "presidents assistant",
        "executive support",
    ],
    "board_support": [
        "board coordinator",
        "trustee coordinator",
        "board liaison",
        "trustee liaison",
        "board secretary",
        "secretary to the board",
        "clerk of the board",
        "governance coordinator",
        "governance liaison",
    ],
    "senior_leadership": [
        "vice president",
        "vp ",
        "provost",
        "executive director",
        "chief of staff",
        "chief financial officer",
        "chief information officer",
        "chief human resources",
        "chief diversity",
        "chief academic",
        "chief student",
    ],
}
def _looks_like_person_name(text: str) -> bool:
    """
    Detects likely person names on leadership pages while rejecting headings,
    navigation labels, and descriptive phrases.
    """
    if not text:
        return False

    value = " ".join(text.strip().split())

    if len(value) < 5 or len(value) > 70:
        return False

    lower_value = value.lower()

    blocked_phrases = [
        "college",
        "committee",
        "department",
        "division",
        "office",
        "administration",
        "leadership",
        "executive team",
        "president's team",
        "presidents team",
        "board",
        "trustees",
        "contact",
        "email",
        "phone",
        "fax",
        "campus",
        "services",
        "student",
        "about",
        "home",
        "menu",
        "search",
        "biography",
        "welcome",
        "all star",
        "vice presidents",
        "vice-presidents",
        "president &",
        "president and",
        "connect to",
        "meet the",
        "our team",
        "read more",
        "learn more",
    ]

    if any(phrase in lower_value for phrase in blocked_phrases):
        return False

    if "&" in value:
        return False

    if ":" in value:
        return False

    if value.endswith((".", "!", "?", ":")):
        return False

    parts = value.replace(",", " ").split()

    if len(parts) < 2 or len(parts) > 5:
        return False

    allowed_prefixes = {
        "Dr.",
        "Dr",
        "Mr.",
        "Mr",
        "Ms.",
        "Ms",
        "Mrs.",
        "Mrs",
    }

    name_parts = [
        part
        for part in parts
        if part not in allowed_prefixes
    ]

    if len(name_parts) < 2 or len(name_parts) > 4:
        return False

    capitalized_count = 0

    for part in name_parts:
        cleaned = part.strip(".,()[]{}'\"")

        if not cleaned:
            continue

        if not any(character.isalpha() for character in cleaned):
            return False

        if cleaned[0].isupper():
            capitalized_count += 1

    return capitalized_count == len(name_parts)


def _looks_like_leadership_title(text: str) -> bool:
    """
    Detects likely executive or senior-leadership job titles while rejecting
    descriptive sentences, navigation text, and page headings.
    """
    if not text:
        return False

    value = " ".join(text.strip().split())

    if len(value) < 5 or len(value) > 100:
        return False

    lower_value = value.lower()

    title_keywords = [
        "president",
        "chancellor",
        "vice president",
        "vice-president",
        "executive director",
        "executive officer",
        "chief",
        "provost",
        "dean",
        "director",
        "officer",
    ]

    blocked_phrases = [
        "copyright",
        "privacy",
        "accessibility",
        "facebook",
        "instagram",
        "linkedin",
        "youtube",
        "twitter",
        "search",
        "menu",
        "home",
        "connect to",
        "learn more",
        "read more",
        "click here",
        "view college",
        "welcome to",
        "all star team",
        "biography",
        "serves as",
        "joined the",
        "has served",
        "is responsible",
        "is committed",
        "works to",
    ]

    if any(phrase in lower_value for phrase in blocked_phrases):
        return False

    if value.endswith((".", "!", "?")):
        return False

    if len(value.split()) > 12:
        return False

    return any(
        keyword in lower_value
        for keyword in title_keywords
    )
def _extract_name_from_president_biography_line(text: str) -> str:
    """
    Extracts a person's name from biography text such as:

        Bob Mohrbacher has been president of Centralia College since 2016.
    """
    if not text:
        return ""

    value = " ".join(text.strip().split())

    biography_markers = [
        " has been ",
        " is the ",
        " serves as ",
        " joined ",
        " became ",
        " was appointed ",
    ]

    lower_value = value.lower()

    marker_position = -1

    for marker in biography_markers:
        position = lower_value.find(marker)

        if position > 0:
            marker_position = position
            break

    if marker_position == -1:
        return ""

    possible_name = value[:marker_position].strip(" ,.-")

    if not _looks_like_person_name(possible_name):
        return ""

    return possible_name

def extract_leadership_contacts_from_fetched_pages(
    fetched_pages: list[dict],
) -> list[dict]:
    """
    Extracts name/title leadership records from fetched leadership pages.

    Supports both:
        Name
        Title

    and:
        Title
        Name followed by biography text
    """
    leadership_contacts = []

    for fetched_page in fetched_pages:
        if fetched_page.get("category") != "leadership":
            continue

        if fetched_page.get("status") != "fetched":
            continue

        organization = fetched_page.get("organization", "")

        source_page_title = (
            fetched_page.get("source_page_title")
            or fetched_page.get("page_title")
            or ""
        )

        fetched_title = (
            fetched_page.get("title")
            or fetched_page.get("fetched_title")
            or ""
        )

        source_url = fetched_page.get("url", "")
        page_text = fetched_page.get("text", "")

        if not page_text:
            continue

        lines = [
            " ".join(line.strip().split())
            for line in page_text.splitlines()
            if line and line.strip()
        ]

        for index in range(len(lines) - 1):
            current_line = lines[index]
            next_line = lines[index + 1]

            # Standard pattern:
            # Name
            # Title
            if (
                _looks_like_person_name(current_line)
                and _looks_like_leadership_title(next_line)
            ):
                leadership_contacts.append(
                    {
                        "organization": organization,
                        "source_page_title": source_page_title,
                        "fetched_title": fetched_title,
                        "source_url": source_url,
                        "name": current_line,
                        "title": next_line,
                        "department": "",
                        "phone": "",
                        "email": "",
                        "source_type": "leadership_page",
                    }
                )

                continue

            # Title-first biography pattern:
            # President
            # Bob Mohrbacher has been president...
            if _looks_like_leadership_title(current_line):
                biography_name = (
                    _extract_name_from_president_biography_line(
                        next_line
                    )
                )

                if biography_name:
                    leadership_contacts.append(
                        {
                            "organization": organization,
                            "source_page_title": source_page_title,
                            "fetched_title": fetched_title,
                            "source_url": source_url,
                            "name": biography_name,
                            "title": current_line,
                            "department": "",
                            "phone": "",
                            "email": "",
                            "source_type": "leadership_page",
                        }
                    )

    unique_contacts = []
    seen_people = set()

    for contact in leadership_contacts:
        person_key = (
            contact.get("organization", "").lower().strip(),
            _normalize_contact_name_for_matching(
                contact.get("name", "")
            ),
            contact.get("source_url", "").lower().strip(),
        )

        if person_key in seen_people:
            continue

        seen_people.add(person_key)
        unique_contacts.append(contact)

    return unique_contacts

def summarize_leadership_contacts(leadership_contacts: list[dict]) -> None:
    """
    Prints a concise summary of leadership-page contacts.
    """
    print("\nLeadership-page contacts")
    print("------------------------")
    print(f"Leadership contacts found: {len(leadership_contacts)}")

    if not leadership_contacts:
        return

    organizations = sorted(
        {
            contact.get("organization", "")
            for contact in leadership_contacts
            if contact.get("organization", "")
        }
    )

    print(f"Organizations with leadership contacts: {len(organizations)}")

    for contact in leadership_contacts[:15]:
        print()
        print(f"Organization: {contact.get('organization', '')}")
        print(f"Name: {contact.get('name', '')}")
        print(f"Title: {contact.get('title', '')}")
        print(f"Source: {contact.get('source_url', '')}")

def normalize_role_text(value: str) -> str:
    """
    Normalizes role/title text for role-target matching.
    """
    if not value:
        return ""

    return " ".join(value.lower().replace("&", " and ").split())

def role_text_contains_phrase(text: str, phrase: str) -> bool:
    """
    Checks whether a normalized role phrase appears in normalized text.

    This helps avoid treating the word 'president' inside
    'vice president' as a standalone president/chancellor match.
    """
    if not text or not phrase:
        return False

    pattern = rf"\b{re.escape(phrase)}\b"

    return re.search(pattern, text) is not None


def is_true_president_chancellor_match(
    combined_text: str,
    title: str,
    department: str,
    keyword: str,
) -> bool:
    """
    Prevents false positives where 'president' appears only as part of
    'vice president'.

    Examples:
    - President -> true
    - President's Office -> true
    - Executive Assistant to the President -> true
    - Vice President -> false for president_chancellor
    """
    keyword = normalize_role_text(keyword)

    if keyword == "president":
        if "vice president" in combined_text:
            cleaned_text = combined_text.replace("vice president", "")

            if not role_text_contains_phrase(cleaned_text, "president"):
                return False

        return role_text_contains_phrase(combined_text, "president")

    if keyword == "chancellor":
        if "vice chancellor" in combined_text:
            cleaned_text = combined_text.replace("vice chancellor", "")

            if not role_text_contains_phrase(cleaned_text, "chancellor"):
                return False

        return role_text_contains_phrase(combined_text, "chancellor")

    return role_text_contains_phrase(combined_text, keyword)


def classify_contact_role_target(contact: dict) -> dict:
    """
    Classifies whether a structured contact appears to be a high-value role target.

    President/chancellor classification is based primarily on the person's title,
    not merely on working in the President's Office.
    """
    title = normalize_role_text(contact.get("title", ""))
    department = normalize_role_text(contact.get("department", ""))

    combined_text = f"{title} {department}".strip()

    matched_categories = []
    matched_terms = []

    assistant_title_phrases = [
        "executive assistant",
        "exec asst",
        "administrative assistant",
        "admin assistant",
        "assistant to the president",
        "assistant to president",
        "president's assistant",
        "presidents assistant",
    ]

    is_assistant_title = any(
        role_text_contains_phrase(title, phrase)
        for phrase in assistant_title_phrases
    )

    for role_category, keywords in ROLE_TARGET_KEYWORDS.items():
        for keyword in keywords:
            normalized_keyword = normalize_role_text(keyword)

            if not normalized_keyword:
                continue

            if role_category == "president_chancellor":
                # Do not classify assistants as presidents merely because their
                # title or department includes the word "president."
                if is_assistant_title:
                    matched = False
                else:
                    matched = is_true_president_chancellor_match(
                        combined_text=title,
                        title=title,
                        department="",
                        keyword=normalized_keyword,
                    )
            else:
                matched = role_text_contains_phrase(
                    combined_text,
                    normalized_keyword,
                )

            if matched:
                matched_categories.append(role_category)
                matched_terms.append(keyword)

    unique_categories = []

    for category in matched_categories:
        if category not in unique_categories:
            unique_categories.append(category)

    unique_terms = []

    for term in matched_terms:
        if term not in unique_terms:
            unique_terms.append(term)

    priority_score = 0

    if "president_chancellor" in unique_categories:
        priority_score += 100

    if "executive_assistant" in unique_categories:
        priority_score += 90

    if "board_support" in unique_categories:
        priority_score += 85

    if "senior_leadership" in unique_categories:
        priority_score += 60

    # Department context can increase priority, but it should not create
    # a president/chancellor classification by itself.
    if "president" in department:
        priority_score += 15

    if "board" in department or "trustee" in department:
        priority_score += 15

    if "executive" in title or "exec asst" in title:
        priority_score += 10

    is_role_target = priority_score > 0

    classified_contact = contact.copy()
    classified_contact["is_role_target"] = is_role_target
    classified_contact["role_categories"] = unique_categories
    classified_contact["matched_role_terms"] = unique_terms
    classified_contact["role_priority_score"] = priority_score

    return classified_contact
def _normalize_contact_name_for_matching(name: str) -> str:
    """
    Normalizes a person's name so records such as 'Dr. Eric Murray' and
    'Eric Murray' can be matched.
    """
    if not name:
        return ""

    value = " ".join(name.lower().strip().split())

    prefixes = [
        "dr. ",
        "dr ",
        "mr. ",
        "mr ",
        "ms. ",
        "ms ",
        "mrs. ",
        "mrs ",
    ]

    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix):]
            break

    return value.strip()

def merge_duplicate_contacts_across_sources(
    contacts: list[dict],
) -> list[dict]:
    """
    Merges the same person only when found across different source types.

    A directory-page record is preferred because it is more likely to contain
    email, phone, and department information. Records from the same source type
    are not merged solely because they share a name.
    """
    merged_contacts = []
    contact_positions = {}

    for contact in contacts:
        organization = contact.get("organization", "").strip()
        name = contact.get("name", "").strip()
        source_type = contact.get("source_type", "").strip()

        normalized_name = _normalize_contact_name_for_matching(name)

        if not organization or not normalized_name:
            merged_contacts.append(dict(contact))
            continue

        person_key = (
            organization.lower(),
            normalized_name,
        )

        existing_position = contact_positions.get(person_key)

        if existing_position is None:
            prepared_contact = dict(contact)
            prepared_contact["additional_source_page_titles"] = []
            prepared_contact["additional_source_urls"] = []
            prepared_contact["additional_source_types"] = []

            merged_contacts.append(prepared_contact)
            contact_positions[person_key] = len(merged_contacts) - 1
            continue

        existing = merged_contacts[existing_position]
        existing_source_type = existing.get("source_type", "").strip()

        # Do not merge records from the same source type.
        if source_type == existing_source_type:
            separate_contact = dict(contact)
            separate_contact["additional_source_page_titles"] = []
            separate_contact["additional_source_urls"] = []
            separate_contact["additional_source_types"] = []

            merged_contacts.append(separate_contact)
            continue

        valid_cross_source_pair = {
            source_type,
            existing_source_type,
        } == {
            "directory_page",
            "leadership_page",
        }

        if not valid_cross_source_pair:
            separate_contact = dict(contact)
            separate_contact["additional_source_page_titles"] = []
            separate_contact["additional_source_urls"] = []
            separate_contact["additional_source_types"] = []

            merged_contacts.append(separate_contact)
            continue

        # Prefer the directory record as the primary record.
        if source_type == "directory_page":
            primary = dict(contact)
            secondary = existing
        else:
            primary = existing
            secondary = contact

        primary.setdefault("additional_source_page_titles", [])
        primary.setdefault("additional_source_urls", [])
        primary.setdefault("additional_source_types", [])

        secondary_title = secondary.get("source_page_title", "")
        secondary_url = secondary.get("source_url", "")
        secondary_type = secondary.get("source_type", "")

        if (
            secondary_title
            and secondary_title != primary.get("source_page_title", "")
            and secondary_title
            not in primary["additional_source_page_titles"]
        ):
            primary["additional_source_page_titles"].append(
                secondary_title
            )

        if (
            secondary_url
            and secondary_url != primary.get("source_url", "")
            and secondary_url not in primary["additional_source_urls"]
        ):
            primary["additional_source_urls"].append(
                secondary_url
            )

        if (
            secondary_type
            and secondary_type != primary.get("source_type", "")
            and secondary_type not in primary["additional_source_types"]
        ):
            primary["additional_source_types"].append(
                secondary_type
            )

        for field in [
            "title",
            "department",
            "phone",
            "email",
        ]:
            if not primary.get(field) and secondary.get(field):
                primary[field] = secondary.get(field)

        merged_contacts[existing_position] = primary

    return merged_contacts

def classify_role_targets_from_contacts(contacts: list[dict]) -> list[dict]:
    """
    Applies role-target classification to structured contacts.
    """
    classified_contacts = []

    for contact in contacts:
        classified_contacts.append(classify_contact_role_target(contact))

    classified_contacts.sort(
        key=lambda item: item.get("role_priority_score", 0),
        reverse=True,
    )

    return classified_contacts


def filter_role_target_contacts(classified_contacts: list[dict]) -> list[dict]:
    """
    Returns only contacts flagged as role targets.
    """
    role_targets = []

    for contact in classified_contacts:
        if contact.get("is_role_target"):
            role_targets.append(contact)

    return role_targets


def summarize_role_target_contacts(role_targets: list[dict]) -> dict:
    """
    Summarizes role-target contacts by category.
    """
    summary = {
        "total_role_targets": len(role_targets),
        "by_role_category": {},
    }

    for contact in role_targets:
        categories = contact.get("role_categories", [])

        for category in categories:
            if category not in summary["by_role_category"]:
                summary["by_role_category"][category] = 0

            summary["by_role_category"][category] += 1

    return summary

def fetch_html_page_texts_balanced_by_organization(
    page_records: list[dict],
    pages_per_organization: int = 3,
    max_total_fetched: int = 25,
    skip_review_pages: bool = True,
    allowed_categories: tuple[str, ...] = ("directory", "leadership", "board"),
) -> list[dict]:
    """
    Fetches pages in a balanced way across organizations.

    Instead of allowing one college to consume the whole fetch limit,
    this tries to fetch a few useful pages per institution before moving on.

    Default priority:
    1. directory
    2. leadership
    3. board

    Strategic plan pages are excluded by default because this stage is focused
    on contacts and outreach targets.
    """
    category_priority = {
        "directory": 1,
        "leadership": 2,
        "board": 3,
        "strategic_plan": 4,
    }

    grouped_pages = {}
    organization_order = []

    for page_record in page_records:
        organization = page_record.get("organization", "")
        category = page_record.get("category", "")

        if not organization:
            continue

        if allowed_categories and category not in allowed_categories:
            continue

        if skip_review_pages and page_record.get("needs_review"):
            continue

        if organization not in grouped_pages:
            grouped_pages[organization] = []
            organization_order.append(organization)

        grouped_pages[organization].append(page_record)

    for organization, pages in grouped_pages.items():
        pages.sort(
            key=lambda page: (
                category_priority.get(page.get("category", ""), 99),
                -page.get("score", 0),
            )
        )

    fetched_results = []
    total_successfully_fetched = 0
    seen_urls = set()

    for organization in organization_order:
        successful_for_organization = 0
        pages = grouped_pages.get(organization, [])

        for page_record in pages:
            if successful_for_organization >= pages_per_organization:
                break

            if total_successfully_fetched >= max_total_fetched:
                return fetched_results

            url = page_record.get("url", "")

            if not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            result = fetch_html_page_text(page_record)
            fetched_results.append(result)

            if result.get("status") == "fetched":
                successful_for_organization += 1
                total_successfully_fetched += 1

    return fetched_results