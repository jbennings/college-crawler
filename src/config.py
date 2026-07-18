from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "input" / "california_community_college_districts_chancellors.xlsx"

INPUT_SHEET_NAME = "Community Colleges "

REQUIRED_COLUMNS = [
    "Org ID",
    "Organization",
    "Institution Type",
    "District",
    "State",
    "Region",
    "Website",
    "Board Page",
    "Chancellor",
    "Chancellor Phone",
    "Chancellor Address",
    "Chancellor Email",
    "President/CEO",
    "Appointed",
    "Interim (Y/N)",
    "Primary Email",
    "Primary Phone",
    "Executive Assistant/Office Manager",
    "Executive Assistant Email",
    "Mailing Address",
    "President's Workplan",
    "Notes",
    "Last Verified Date",
]