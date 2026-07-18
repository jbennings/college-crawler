"""
page_classifier.py

Scores and classifies discovered links into useful prospecting categories:
- leadership
- board
- directory
- strategic_plan

This version reduces false positives from:
- student life / student leadership
- admissions / tuition / financial aid pages
- dashboards accidentally matching "board"
- academic program pages
- generic copy-anchor links
- weak strategic-plan matches based only on "mission" or "vision"

It also decodes URLs before scoring so filenames like:
    Strategic%20Plan%202024.pdf
are scored correctly.
"""

import re
from urllib.parse import urlparse, unquote


CATEGORY_RULES = {
    "leadership": {
        "strong_phrases": [
            "office of the president",
            "president's office",
            "presidents office",
            "president and cabinet",
            "executive leadership",
            "executive team",
            "senior leadership",
            "college leadership",
            "administrative leadership",
            "leadership team",
            "president",
            "chancellor",
            "superintendent/president",
            "superintendent president",
            "cabinet",
            "administration",
        ],
        "medium_phrases": [
            "about the president",
            "meet the president",
            "message from the president",
            "executive cabinet",
            "president biography",
            "president bio",
            "administrative services",
            "college administration",
        ],
        "url_terms": [
            "president",
            "chancellor",
            "cabinet",
            "executive",
            "leadership",
            "administration",
        ],
    },
    "board": {
        "strong_phrases": [
            "board of trustees",
            "board of directors",
            "board members",
            "board meeting",
            "board meetings",
            "board meeting schedule",
            "trustees",
            "governing board",
            "college governance",
            "district board",
            "board chair",
            "board vice chair",
        ],
        "medium_phrases": [
            "governance",
            "board agenda",
            "board minutes",
            "elected trustees",
            "trustee area",
        ],
        "url_terms": [
            "board",
            "trustees",
            "governance",
            "governing-board",
        ],
    },
    "directory": {
        "strong_phrases": [
            "employee directory",
            "staff directory",
            "faculty and staff directory",
            "faculty & staff directory",
            "campus directory",
            "directory",
            "contact directory",
        ],
        "medium_phrases": [
            "contact us",
            "contacts",
            "staff",
            "faculty and staff",
            "departments",
            "offices",
        ],
        "url_terms": [
            "directory",
            "contact",
            "contacts",
            "staff",
            "faculty-staff",
            "faculty_and_staff",
            "offices",
        ],
    },
    "strategic_plan": {
        "strong_phrases": [
            "strategic plan",
            "strategic planning",
            "institutional strategic plan",
            "college strategic plan",
            "district strategic plan",
            "strategic priorities",
            "mission vision values",
            "mission, vision, values",
            "mission vision guiding principles",
            "educational master plan",
            "facilities master plan",
        ],
        "medium_phrases": [
            "institutional effectiveness",
            "planning",
            "vision",
            "mission",
            "goals",
            "priorities",
            "master plan",
            "comprehensive plan",
        ],
        "url_terms": [
            "strategic-plan",
            "strategicplanning",
            "strategic-planning",
            "strategic",
            "planning",
            "institutional-effectiveness",
            "institutionaleffectiveness",
            "master-plan",
            "mission",
            "vision",
        ],
    },
}


NEGATIVE_CONTEXTS = {
    "leadership": {
        "phrases": [
            "student leadership",
            "student life",
            "student government",
            "student senate",
            "associated students",
            "student club",
            "student clubs",
            "club leadership",
            "leadership program",
            "leadership academy",
            "leadership certificate",
            "leadership course",
            "leadership class",
            "leadership development program",
            "emerging leaders",
            "peer mentor",
            "student ambassador",
            "community engagement officer",
            "events and advocacy board",
            "phi theta kappa",
            "president's friday letters",
            "presidents friday letters",
            "friday letters",
            "newsletter",
            "newsroom",
            "bachelor of applied science",
            "associate of applied science",
            "certificate program",
            "degree program",
            "edi assessment",
            "executive summary and recommendations",
            "assessment",
            "recommendations",
        ],
        "url_terms": [
            "student-life",
            "student_life",
            "studentlife",
            "students",
            "student",
            "clubs",
            "club",
            "activities",
            "athletics",
            "programs",
            "program",
            "academic-programs",
            "academics",
            "courses",
            "course",
            "catalog",
            "degrees",
            "degree",
            "certificate",
            "certificates",
            "class-schedule",
            "schedule",
            "enrollment",
            "admissions",
            "admission",
            "financial-aid",
            "tuition",
            "payment",
            "payment-plan",
            "workforce",
            "continuing-education",
            "kodiak-cave",
            "phi-theta-kappa",
            "news",
            "newsroom",
            "letters",
            "blog",
            "article",
            "assessment",
            "recommendations",
        ],
    },
    "board": {
        "phrases": [
            "student board",
            "events and advocacy board",
            "advisory board",
            "program advisory board",
            "foundation board",
            "alumni board",
            "non-discrimination",
            "nondiscrimination",
            "policy",
            "policies",
            "data dashboard",
            "data dashboards",
            "dashboard",
            "dashboards",
        ],
        "url_terms": [
            "student-life",
            "student",
            "students",
            "advisory",
            "foundation",
            "alumni",
            "clubs",
            "activities",
            "events",
            "policy",
            "policies",
            "non-discrimination",
            "nondiscrimination",
            "dashboard",
            "dashboards",
            "data-dashboards",
        ],
    },
    "directory": {
        "phrases": [
            "student directory",
            "course directory",
            "program directory",
            "forms directory",
            "employee benefits",
        ],
        "url_terms": [
            "course",
            "courses",
            "catalog",
            "program",
            "programs",
            "student",
            "students",
            "forms",
            "form",
        ],
    },
    "strategic_plan": {
        "phrases": [
            "student education plan",
            "academic plan for students",
            "payment plan",
            "degree plan",
            "program plan",
            "read more",
            "news",
            "newsroom",
            "article",
            "award",
            "newsletter",
            "admissions",
            "admission",
            "outreach & admissions",
            "outreach and admissions",
            "financial aid",
            "scholarships",
            "schedule a campus tour",
            "campus tour",
            "virtual welcome center",
            "welcome center",
            "pay for college",
            "paying for college",
            "bachelor of applied science",
            "associate of applied science",
            "certificate program",
            "degree program",
            "area of study",
            "creative and communication arts",
            "office supervision and management",
        ],
        "url_terms": [
            "payment-plan",
            "student",
            "students",
            "degree",
            "program",
            "programs",
            "academic-programs",
            "academics",
            "course",
            "courses",
            "catalog",
            "news",
            "newsroom",
            "article",
            "blog",
            "award",
            "admissions",
            "admission",
            "admission-and-tuition",
            "tuition",
            "financial-aid",
            "scholarships",
            "student-center",
            "student-resources",
            "academic-support",
            "outreach-and-recruiting",
            "tour",
            "virtual-welcome-center",
            "paying-for-college",
            "getstarted",
        ],
    },
}


GENERIC_LINK_TEXT = [
    "read more",
    "learn more",
    "more",
    "click here",
    "view more",
    "copied copy a link to this section",
    "copy a link to this section",
    "copied!",
]


GLOBAL_NEGATIVE_URL_TERMS = [
    "wp-content",
    "calendar",
    "event",
    "events",
    "news",
    "newsroom",
    "article",
    "blog",
    "apply",
    "application",
    "login",
    "portal",
    "library",
    "bookstore",
    "map",
    "maps",
    "parking",
    "transcript",
    "forms",
    "form",
    "jobs",
    "careers",
    "employment",
    "donate",
    "foundation",
]


def normalize_text(value: str) -> str:
    if value is None:
        return ""

    value = unquote(str(value).lower())
    value = value.replace("_", " ").replace("-", " ").replace("/", " ")
    value = re.sub(r"[^a-z0-9&']+", " ", value)

    return " ".join(value.split())


def get_url_path(url: str) -> str:
    try:
        parsed = urlparse(url)
        return normalize_text(parsed.path)
    except Exception:
        return ""


def get_url_tokens(url: str) -> set[str]:
    path = get_url_path(url)
    return set(path.split())


def is_academic_program_context(text: str, path: str, tokens: set[str]) -> bool:
    combined = f"{text} {path}".strip()

    academic_phrases = [
        "bachelor of applied science",
        "associate of applied science",
        "certificate program",
        "degree program",
        "area of study",
        "academic program",
        "academic programs",
    ]

    academic_tokens = {
        "program",
        "programs",
        "academic",
        "academics",
        "degree",
        "degrees",
        "certificate",
        "certificates",
        "course",
        "courses",
        "catalog",
    }

    if any(phrase in combined for phrase in academic_phrases):
        return True

    if tokens.intersection(academic_tokens):
        return True

    return False


def score_for_category(link_text: str, url: str, category: str) -> tuple[int, list[str]]:
    text = normalize_text(link_text)
    path = get_url_path(url)
    tokens = get_url_tokens(url)
    combined = f"{text} {path}".strip()

    rules = CATEGORY_RULES[category]
    score = 0
    reasons = []

    for phrase in rules["strong_phrases"]:
        phrase_norm = normalize_text(phrase)
        if phrase_norm and phrase_norm in combined:
            score += 10
            reasons.append(f"strong phrase: {phrase}")

    for phrase in rules["medium_phrases"]:
        phrase_norm = normalize_text(phrase)
        if phrase_norm and phrase_norm in combined:
            score += 5
            reasons.append(f"medium phrase: {phrase}")

    for term in rules["url_terms"]:
        term_norm = normalize_text(term)

        if not term_norm:
            continue

        if " " in term_norm:
            if term_norm in path:
                score += 5
                reasons.append(f"url match: {term}")
        else:
            if term_norm in tokens:
                score += 5
                reasons.append(f"url match: {term}")

    negative = NEGATIVE_CONTEXTS.get(category, {})

    for phrase in negative.get("phrases", []):
        phrase_norm = normalize_text(phrase)
        if phrase_norm and phrase_norm in combined:
            score -= 12
            reasons.append(f"negative context: {phrase}")

    for term in negative.get("url_terms", []):
        term_norm = normalize_text(term)

        if not term_norm:
            continue

        if " " in term_norm:
            if term_norm in path:
                score -= 8
                reasons.append(f"negative url context: {term}")
        else:
            if term_norm in tokens:
                score -= 8
                reasons.append(f"negative url context: {term}")

    for term in GLOBAL_NEGATIVE_URL_TERMS:
        term_norm = normalize_text(term)
        if term_norm and term_norm in tokens:
            score -= 3
            reasons.append(f"global negative url context: {term}")

    if text in GENERIC_LINK_TEXT:
        score -= 30
        reasons.append(f"generic link text penalty: {text}")

    # Academic program pages should almost never be classified as executive
    # leadership or strategic planning pages.
    if category in ("leadership", "strategic_plan") and is_academic_program_context(
        text,
        path,
        tokens,
    ):
        score -= 20
        reasons.append("negative context: academic program page")

    if category == "leadership":
        if "president" in combined or "chancellor" in combined:
            score += 8
            reasons.append("precision bonus: president/chancellor")
        if "executive" in combined and ("team" in combined or "cabinet" in combined):
            score += 6
            reasons.append("precision bonus: executive team/cabinet")

    if category == "board":
        if "trustees" in combined:
            score += 8
            reasons.append("precision bonus: trustees")
        if "board of" in combined:
            score += 8
            reasons.append("precision bonus: board of")

    if category == "strategic_plan":
        if "strategic plan" in combined or "strategic planning" in combined:
            score += 8
            reasons.append("precision bonus: strategic plan/planning")
        if "institutional effectiveness" in combined:
            score += 6
            reasons.append("precision bonus: institutional effectiveness")

    if category == "directory":
        if "employee directory" in combined or "staff directory" in combined:
            score += 8
            reasons.append("precision bonus: employee/staff directory")

    return max(score, 0), reasons


def classify_link(link_text: str, url: str) -> list[dict]:
    results = []

    for category in CATEGORY_RULES:
        score, reasons = score_for_category(link_text, url, category)

        if score > 0:
            results.append(
                {
                    "category": category,
                    "score": score,
                    "reasons": reasons,
                }
            )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results