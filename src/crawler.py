"""
crawler.py

Website checking and internal page discovery for College Crawler.

Step 7 update:
1. Keeps Step 6 homepage discovery and spreadsheet URL validation.
2. Adds targeted one-level crawling from the best discovered pages.
3. Does NOT crawl entire websites.
4. Does NOT extract contacts yet.
5. Preserves compatibility with the existing main.py display format.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

from page_classifier import classify_link


REQUEST_TIMEOUT_SECONDS = 15
MIN_DISCOVERY_SCORE = 5
MAX_RESULTS_PER_CATEGORY = 5

# Step 7 controls
ENABLE_TARGETED_CRAWL = True
MAX_TARGET_PAGES_PER_RECORD = 8
MAX_LINKS_PER_TARGET_PAGE = 100

# Only crawl stronger parent pages.
# This prevents generic pages such as "Offices & Services" from creating noise.
TARGETED_CRAWL_MIN_PARENT_SCORE = 15
DIRECTORY_TARGETED_CRAWL_MIN_PARENT_SCORE = 25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


COMMON_SECOND_LEVEL_SUFFIXES = {
    "co.uk",
    "ac.uk",
    "gov.uk",
    "org.uk",
    "com.au",
    "edu.au",
    "gov.au",
    "co.nz",
    "org.nz",
    "com.br",
    "com.mx",
}


TRUSTED_EXTERNAL_HOST_HINTS = [
    "boarddocs.com",
    "go.boarddocs.com",
    "diligent.community",
    "diligent.com",
    "google.com",
    "drive.google.com",
    "docs.google.com",
    "dropbox.com",
    "sharepoint.com",
    "onedrive.live.com",
    "adobe.com",
    "issuu.com",
]


@dataclass
class WebsiteCheckResult:
    url: str
    final_url: str
    status: str
    status_code: int | None
    error: str = ""


def normalize_url(url: str) -> str:
    """
    Cleans and standardizes a URL.

    Important:
    Does not convert plain text like 'Edmonds Board' into a fake URL.
    """
    if not url:
        return ""

    url = str(url).strip()

    if not url:
        return ""

    if " " in url and not url.lower().startswith(("http://", "https://")):
        return ""

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    url, _fragment = urldefrag(url)
    return url


def get_hostname(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().strip()

        if host.startswith("www."):
            host = host[4:]

        return host

    except Exception:
        return ""


def get_root_domain(url_or_host: str) -> str:
    host = url_or_host.lower().strip()

    if "://" in host:
        host = get_hostname(host)

    if host.startswith("www."):
        host = host[4:]

    parts = [part for part in host.split(".") if part]

    if len(parts) <= 2:
        return host

    last_two = ".".join(parts[-2:])
    last_three = ".".join(parts[-3:])

    if last_two in COMMON_SECOND_LEVEL_SUFFIXES and len(parts) >= 3:
        return last_three

    return last_two


def same_or_related_domain(candidate_url: str, institution_website: str) -> bool:
    candidate_root = get_root_domain(candidate_url)
    institution_root = get_root_domain(institution_website)

    if not candidate_root or not institution_root:
        return False

    return candidate_root == institution_root


def is_trusted_external_domain(candidate_url: str) -> bool:
    host = get_hostname(candidate_url)

    for trusted in TRUSTED_EXTERNAL_HOST_HINTS:
        if host == trusted or host.endswith("." + trusted):
            return True

    return False


def validate_candidate_url(candidate_url: str, institution_website: str) -> dict:
    candidate_url = normalize_url(candidate_url)
    institution_website = normalize_url(institution_website)

    candidate_root = get_root_domain(candidate_url)
    institution_root = get_root_domain(institution_website)

    candidate_host = get_hostname(candidate_url)

    if candidate_url and "." not in candidate_host:
        return {
            "validation_status": "invalid",
            "validation_reason": "candidate value does not appear to be a valid URL",
            "candidate_root_domain": candidate_root,
            "institution_root_domain": institution_root,
        }

    if not candidate_url:
        return {
            "validation_status": "invalid",
            "validation_reason": "empty URL",
            "candidate_root_domain": "",
            "institution_root_domain": institution_root,
        }

    if not institution_website:
        return {
            "validation_status": "review_missing_institution_website",
            "validation_reason": "institution website missing; cannot validate candidate domain",
            "candidate_root_domain": candidate_root,
            "institution_root_domain": "",
        }

    if same_or_related_domain(candidate_url, institution_website):
        return {
            "validation_status": "trusted_same_root_domain",
            "validation_reason": "candidate URL shares the same root domain as the institution website",
            "candidate_root_domain": candidate_root,
            "institution_root_domain": institution_root,
        }

    if is_trusted_external_domain(candidate_url):
        return {
            "validation_status": "trusted_external_domain",
            "validation_reason": "candidate URL is on a known document/governance hosting platform",
            "candidate_root_domain": candidate_root,
            "institution_root_domain": institution_root,
        }

    return {
        "validation_status": "review_unrelated_domain",
        "validation_reason": "candidate URL root domain differs from institution website root domain",
        "candidate_root_domain": candidate_root,
        "institution_root_domain": institution_root,
    }


def check_website(url: str) -> WebsiteCheckResult:
    url = normalize_url(url)

    if not url:
        return WebsiteCheckResult(
            url=url,
            final_url="",
            status="invalid",
            status_code=None,
            error="Missing URL",
        )

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )

        status_code = response.status_code
        final_url = response.url

        if status_code == 200:
            status = "reachable"
        elif status_code in (401, 403):
            status = "blocked"
        elif status_code == 429:
            status = "rate_limited"
        elif status_code == 404:
            status = "not_found"
        elif 500 <= status_code <= 599:
            status = "server_error"
        else:
            status = "request_error"

        return WebsiteCheckResult(
            url=url,
            final_url=final_url,
            status=status,
            status_code=status_code,
        )

    except requests.exceptions.Timeout as exc:
        return WebsiteCheckResult(
            url=url,
            final_url="",
            status="timeout",
            status_code=None,
            error=str(exc),
        )

    except requests.exceptions.ConnectionError as exc:
        return WebsiteCheckResult(
            url=url,
            final_url="",
            status="connection_error",
            status_code=None,
            error=str(exc),
        )

    except requests.exceptions.RequestException as exc:
        return WebsiteCheckResult(
            url=url,
            final_url="",
            status="request_error",
            status_code=None,
            error=str(exc),
        )


def check_websites(records: list[dict], limit: int | None = None) -> list[dict]:
    results = []
    records_to_check = records[:limit] if limit else records

    for record in records_to_check:
        organization = record.get("organization", "")
        website = record.get("website", "")

        check_result = check_website(website)

        results.append(
            {
                "organization": organization,
                "website": website,
                "final_url": check_result.final_url,
                "status": check_result.status,
                "status_code": check_result.status_code,
                "error": check_result.error,
            }
        )

    return results


def is_probably_html_url(url: str) -> bool:
    lower_url = url.lower()

    non_html_extensions = (
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
        ".svg",
        ".webp",
        ".zip",
        ".mp4",
        ".mp3",
        ".ics",
    )

    return not lower_url.endswith(non_html_extensions)


def fetch_page_html(url: str) -> tuple[str, str]:
    url = normalize_url(url)

    if not url:
        return "", ""

    if not is_probably_html_url(url):
        return "", url

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )

        if response.status_code != 200:
            return "", response.url

        content_type = response.headers.get("Content-Type", "").lower()

        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            return "", response.url

        return response.text, response.url

    except requests.exceptions.RequestException:
        return "", url


def fetch_homepage_html(url: str) -> tuple[str, str]:
    return fetch_page_html(url)


def is_same_site_link(candidate_url: str, base_url: str) -> bool:
    candidate_host = get_hostname(candidate_url)
    base_host = get_hostname(base_url)

    if not candidate_host or not base_host:
        return False

    return get_root_domain(candidate_host) == get_root_domain(base_host)


def should_skip_link(url: str) -> bool:
    lower_url = url.lower()

    skip_extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".webp",
        ".zip",
        ".mp4",
        ".mp3",
        ".ics",
    )

    if lower_url.startswith(("mailto:", "tel:", "javascript:")):
        return True

    if lower_url.endswith(skip_extensions):
        return True

    return False


def extract_links_from_page(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    links = []

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        link_text = anchor.get_text(" ", strip=True)

        if not href or should_skip_link(href):
            continue

        absolute_url = normalize_url(urljoin(base_url, href))

        if not absolute_url:
            continue

        if not is_same_site_link(absolute_url, base_url):
            continue

        links.append(
            {
                "text": link_text,
                "url": absolute_url,
                "source": "page_link",
            }
        )

        if len(links) >= MAX_LINKS_PER_TARGET_PAGE:
            break

    return links


def extract_links_from_homepage(html: str, base_url: str) -> list[dict]:
    return extract_links_from_page(html, base_url)


def add_candidate(
    grouped_results: dict,
    category: str,
    title: str,
    url: str,
    score: int,
    source: str,
    reasons: list[str] | None = None,
    validation: dict | None = None,
):
    if not url:
        return

    display_text = title or url

    item = {
        "category": category,
        "title": display_text,
        "text": display_text,
        "url": normalize_url(url),
        "score": score,
        "source": source,
        "reasons": reasons or [],
        "retrieved_at": datetime.now().strftime("%Y-%m-%d"),
    }

    if validation:
        item.update(validation)

    grouped_results[category].append(item)


def add_spreadsheet_candidate(
    grouped_results: dict,
    record: dict,
    field_name: str,
    category: str,
    display_title: str,
):
    candidate_url = normalize_url(record.get(field_name, ""))
    institution_website = normalize_url(record.get("website", ""))

    if not candidate_url:
        return

    validation = validate_candidate_url(candidate_url, institution_website)
    status = validation.get("validation_status", "")

    category_fit_score = 0
    category_fit_reasons = []

    classifications = classify_link("", candidate_url)

    for classification in classifications:
        if classification.get("category") == category:
            category_fit_score = classification.get("score", 0)
            category_fit_reasons = classification.get("reasons", [])
            break

    validation["category_fit_score"] = category_fit_score
    validation["category_fit_reasons"] = category_fit_reasons

    if (
        status in ("trusted_same_root_domain", "trusted_external_domain")
        and category_fit_score >= MIN_DISCOVERY_SCORE
    ):
        score = 100
        source = f"spreadsheet_{field_name}_trusted"
        reasons = [
            validation.get("validation_reason", "trusted spreadsheet URL"),
            f"URL appears to match expected category: {category}",
        ]
        reasons.extend(category_fit_reasons)

    elif (
        status in ("trusted_same_root_domain", "trusted_external_domain")
        and category_fit_score < MIN_DISCOVERY_SCORE
    ):
        score = 35
        source = f"spreadsheet_{field_name}_category_review"
        reasons = [
            validation.get("validation_reason", "domain is trusted"),
            f"URL does not strongly match expected category: {category}",
        ]
        reasons.extend(category_fit_reasons)

    else:
        score = 25
        source = f"spreadsheet_{field_name}_review"
        reasons = [
            validation.get(
                "validation_reason",
                "spreadsheet URL requires review",
            )
        ]

    add_candidate(
        grouped_results=grouped_results,
        category=category,
        title=display_title,
        url=candidate_url,
        score=score,
        source=source,
        reasons=reasons,
        validation=validation,
    )


def add_homepage_discovered_candidates(
    grouped_results: dict,
    links: list[dict],
    website: str,
):
    for link in links:
        classifications = classify_link(link["text"], link["url"])

        for classification in classifications:
            category = classification["category"]
            score = classification["score"]
            reasons = classification["reasons"]

            if score < MIN_DISCOVERY_SCORE:
                continue

            add_candidate(
                grouped_results=grouped_results,
                category=category,
                title=link["text"],
                url=link["url"],
                score=score,
                source="homepage_link",
                reasons=reasons,
                validation={
                    "validation_status": "discovered_same_site",
                    "validation_reason": "discovered from institution homepage and shares root domain",
                    "candidate_root_domain": get_root_domain(link["url"]),
                    "institution_root_domain": get_root_domain(website),
                },
            )


def choose_target_pages_for_deeper_crawl(grouped_results: dict) -> list[dict]:
    """
    Chooses a small set of high-value pages to visit one level deeper.

    This intentionally avoids crawling the whole site.

    Step 7 refinement:
    - Crawl trusted board, leadership, and strategic-plan pages.
    - Crawl directory pages only when they are strong enough.
    - Avoid low-score generic pages like Offices & Services, Contact Us, or broad governance pages.
    """
    candidates = []

    preferred_categories = [
        "leadership",
        "board",
        "strategic_plan",
        "directory",
    ]

    for category in preferred_categories:
        items = grouped_results.get(category, [])

        for item in items:
            url = item.get("url", "")
            source = item.get("source", "")
            score = item.get("score", 0)
            validation_status = item.get("validation_status", "")

            if not url:
                continue

            if not is_probably_html_url(url):
                continue

            if validation_status in ("review_unrelated_domain", "invalid"):
                continue

            # Avoid crawling suspicious spreadsheet category-review pages.
            if source.endswith("_category_review"):
                continue

            # Avoid crawling weak parent pages.
            if score < TARGETED_CRAWL_MIN_PARENT_SCORE:
                continue

            # Directory pages can be noisy, so only crawl strong directory pages.
            if category == "directory" and score < DIRECTORY_TARGETED_CRAWL_MIN_PARENT_SCORE:
                continue

            candidates.append(item)

    candidates = sorted(
        candidates,
        key=lambda item: item.get("score", 0),
        reverse=True,
    )

    seen_urls = set()
    unique_candidates = []

    for item in candidates:
        url = item.get("url", "")

        if url in seen_urls:
            continue

        seen_urls.add(url)
        unique_candidates.append(item)

        if len(unique_candidates) >= MAX_TARGET_PAGES_PER_RECORD:
            break

    return unique_candidates

def make_focused_scoring_url(url: str) -> str:
    """
    Creates a simplified URL for scoring targeted child links.

    Why:
    Full child URLs often inherit broad parent-path words like governance,
    leadership, or strategic. That can create false positives.

    Example:
        https://www.cascadia.edu/about/governance-accreditation/expression.aspx

    Full path includes governance, but the final page is really expression.aspx.
    For scoring, we focus on:
        https://www.cascadia.edu/expression.aspx
    """
    url = normalize_url(url)

    if not url:
        return ""

    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]

    if not path_parts:
        return url

    final_part = path_parts[-1]
    focused_path = "/" + final_part

    return f"{parsed.scheme}://{parsed.netloc}{focused_path}"


def add_targeted_crawl_candidates(
    grouped_results: dict,
    website: str,
):
    """
    Visits the best discovered pages and discovers one more level of useful links.

    Step 7 refinement:
    - Scores child links using the link text and final URL segment.
    - Avoids giving too much credit for broad parent paths like /governance-accreditation/.
    - Still allows executive-team profile pages to be retained when they are found
      from an Executive Team parent page.
    """
    target_pages = choose_target_pages_for_deeper_crawl(grouped_results)

    for target in target_pages:
        parent_url = target.get("url", "")
        parent_text = target.get("text", "")
        parent_category = target.get("category", "")

        html, final_url = fetch_page_html(parent_url)

        if not html:
            continue

        links = extract_links_from_page(html, final_url)

        for link in links:
            focused_scoring_url = make_focused_scoring_url(link["url"])
            classifications = classify_link(link["text"], focused_scoring_url)

            # Special case:
            # Executive-team pages often link to individual people by name.
            # The person's name alone may not classify as leadership, but the parent
            # page context is valuable and intentional.
            if (
                parent_category == "leadership"
                and "executive-team" in link["url"].lower()
                and link["url"] != parent_url
            ):
                classifications.append(
                    {
                        "category": "leadership",
                        "score": 21,
                        "reasons": [
                            "inherited leadership context from Executive Team parent page",
                        ],
                    }
                )

            for classification in classifications:
                category = classification["category"]
                score = classification["score"]
                reasons = classification["reasons"]

                if score < MIN_DISCOVERY_SCORE:
                    continue

                add_candidate(
                    grouped_results=grouped_results,
                    category=category,
                    title=link["text"],
                    url=link["url"],
                    score=score,
                    source="targeted_page_link",
                    reasons=[
                        f"found from targeted page: {parent_text}",
                        *reasons,
                    ],
                    validation={
                        "validation_status": "targeted_discovered_same_site",
                        "validation_reason": "discovered from targeted internal page and shares root domain",
                        "candidate_root_domain": get_root_domain(link["url"]),
                        "institution_root_domain": get_root_domain(website),
                        "parent_url": parent_url,
                    },
                )

def discover_useful_pages(record: dict) -> dict:
    grouped_results = defaultdict(list)

    website = normalize_url(record.get("website", ""))

    add_spreadsheet_candidate(
        grouped_results=grouped_results,
        record=record,
        field_name="board_page",
        category="board",
        display_title="Existing spreadsheet Board Page",
    )

    add_spreadsheet_candidate(
        grouped_results=grouped_results,
        record=record,
        field_name="strategic_plan",
        category="strategic_plan",
        display_title="Existing spreadsheet Strategic Plan",
    )

    html, final_url = fetch_homepage_html(website)

    if html:
        homepage_links = extract_links_from_homepage(html, final_url)

        add_homepage_discovered_candidates(
            grouped_results=grouped_results,
            links=homepage_links,
            website=website,
        )

    if ENABLE_TARGETED_CRAWL:
        add_targeted_crawl_candidates(
            grouped_results=grouped_results,
            website=website,
        )

    return rank_grouped_results(grouped_results)


def rank_grouped_results(grouped_results: dict) -> dict:
    final_results = {}

    for category, items in grouped_results.items():
        seen_urls = set()
        unique_items = []

        sorted_items = sorted(items, key=lambda x: x.get("score", 0), reverse=True)

        for item in sorted_items:
            url = item.get("url", "")

            if not url or url in seen_urls:
                continue

            seen_urls.add(url)

            if "text" not in item:
                item["text"] = item.get("title", url)

            if "title" not in item:
                item["title"] = item.get("text", url)

            unique_items.append(item)

        final_results[category] = unique_items[:MAX_RESULTS_PER_CATEGORY]

    for category in ["leadership", "board", "directory", "strategic_plan"]:
        final_results.setdefault(category, [])

    return final_results


def discover_pages_for_records(records: list[dict], limit: int | None = None) -> list[dict]:
    results = []
    records_to_check = records[:limit] if limit else records

    for record in records_to_check:
        organization = record.get("organization", "")
        website = record.get("website", "")

        categories = discover_useful_pages(record)

        results.append(
            {
                "organization": organization,
                "website": website,
                "categories": categories,
            }
        )

    return results


def discover_and_rank_pages(record: dict) -> dict:
    return discover_useful_pages(record)


def find_useful_pages(record: dict) -> dict:
    return discover_useful_pages(record)

def should_page_need_review(page: dict) -> bool:
        """
        Determines whether a discovered page should be flagged for human review.

        Review is needed when:
        - the URL came from an unrelated domain
        - the URL was invalid
        - the spreadsheet URL was on the right domain but did not fit the expected category
        - the score is weak
        """
        validation_status = page.get("validation_status", "")
        source = page.get("source", "")
        score = page.get("score", 0)

        review_statuses = {
            "review_unrelated_domain",
            "invalid",
            "review_missing_institution_website",
        }

        if validation_status in review_statuses:
            return True

        if source.endswith("_review"):
            return True

        if source.endswith("_category_review"):
            return True

        # Weak discovered pages are not necessarily wrong,
        # but they should be reviewed before extraction.
        if score < 10:
            return True

        return False



def flatten_discovered_pages_for_record(record: dict, categories: dict) -> list[dict]:
    """
    Converts grouped discovered pages for one organization into a flat,
    extraction-ready list.

    This does not extract names, emails, or other contact details yet.
    It simply prepares the discovered pages for the future extractor.
    """
    flattened_pages = []

    organization = record.get("organization", "")
    website = record.get("website", "")
    org_id = record.get("org_id", "")
    state = record.get("state", "")
    region = record.get("region", "")

    for category, pages in categories.items():
        for page in pages:
            extraction_record = {
                "org_id": org_id,
                "organization": organization,
                "state": state,
                "region": region,
                "website": website,
                "category": category,
                "page_title": page.get("text", "") or page.get("title", ""),
                "url": page.get("url", ""),
                "score": page.get("score", 0),
                "source": page.get("source", ""),
                "validation_status": page.get("validation_status", ""),
                "validation_reason": page.get("validation_reason", ""),
                "candidate_root_domain": page.get("candidate_root_domain", ""),
                "institution_root_domain": page.get("institution_root_domain", ""),
                "retrieved_at": page.get("retrieved_at", ""),
                "needs_review": should_page_need_review(page),
                "parent_url": page.get("parent_url", ""),
                "reasons": page.get("reasons", []),
            }

            flattened_pages.append(extraction_record)

    flattened_pages.sort(
        key=lambda item: (
            item["organization"],
            item["category"],
            item["needs_review"],
            -item["score"],
        )
    )

    return flattened_pages


def flatten_discovered_pages(results: list[dict], original_records: list[dict]) -> list[dict]:
    """
    Converts all grouped discovery results into one flat list of extraction-ready pages.
    """
    flattened_pages = []

    records_by_org = {
        record.get("organization", ""): record
        for record in original_records
    }

    for result in results:
        organization = result.get("organization", "")
        record = records_by_org.get(organization, {})
        categories = result.get("categories", {})

        flattened_pages.extend(
            flatten_discovered_pages_for_record(
                record=record,
                categories=categories,
            )
        )

    return flattened_pages


def summarize_extraction_readiness(flattened_pages: list[dict]) -> dict:
    """
    Summarizes extraction-ready pages so we can quickly see whether discovery
    is producing enough useful pages for the next phase.
    """
    summary = {
        "total_pages": len(flattened_pages),
        "needs_review": 0,
        "by_category": {},
    }

    for page in flattened_pages:
        category = page.get("category", "unknown")

        if category not in summary["by_category"]:
            summary["by_category"][category] = {
                "total": 0,
                "needs_review": 0,
            }

        summary["by_category"][category]["total"] += 1

        if page.get("needs_review"):
            summary["needs_review"] += 1
            summary["by_category"][category]["needs_review"] += 1

    return summary