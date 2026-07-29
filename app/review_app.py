from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from supabase import Client, create_client
from io import BytesIO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"
FEEDBACK_DIR = PROJECT_ROOT / "data" / "feedback"
FEEDBACK_FILE = FEEDBACK_DIR / "crawler_review_feedback.xlsx"

REVIEWER_NAME = "Adrien"

REVIEW_STATUS_OPTIONS = [
    "Not Reviewed",
    "Correct",
    "Incorrect",
    "Wrong Role",
    "Duplicate",
    "Missing Information",
    "Needs Manual Review",
]


def get_supabase_client() -> Client | None:
    """
    Creates a Supabase client when Streamlit secrets are available.

    Returns None during local development if Supabase secrets
    have not been configured locally.
    """
    try:
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_KEY")
    except Exception:
        return None

    if not supabase_url or not supabase_key:
        return None

    return create_client(
        supabase_url,
        supabase_key,
    )


def get_latest_role_target_file() -> Path | None:
    """
    Returns the most recently modified role-target Excel export.

    Prefers the local data/output folder.
    Falls back to data/sample for deployed environments.
    """
    output_files = list(
        OUTPUT_DIR.glob("role_target_contacts_*.xlsx")
    )

    if output_files:
        return max(
            output_files,
            key=lambda path: path.stat().st_mtime,
        )

    sample_files = list(
        SAMPLE_DIR.glob("role_target_contacts_*.xlsx")
    )

    if sample_files:
        return max(
            sample_files,
            key=lambda path: path.stat().st_mtime,
        )

    return None


def load_latest_role_target_data() -> tuple[pd.DataFrame, Path | None]:
    """
    Loads the newest role-target Excel export.
    """
    latest_file = get_latest_role_target_file()

    if latest_file is None:
        return pd.DataFrame(), None

    df = pd.read_excel(latest_file)

    return df, latest_file


def ensure_feedback_dir() -> None:
    """
    Makes sure the local feedback directory exists.
    """
    FEEDBACK_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def clean_display_value(value) -> str:
    """
    Converts empty or NaN values into a simple dash for display.
    """
    if pd.isna(value):
        return "—"

    text = str(value).strip()

    if not text or text.lower() == "none":
        return "—"

    return text


def clean_storage_value(value) -> str:
    """
    Converts empty values into an empty string for database storage.
    """
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.lower() == "none":
        return ""

    return text


def load_feedback_from_supabase(
    supabase: Client,
) -> pd.DataFrame:
    """
    Loads all saved reviews from Supabase.
    """
    try:
        response = (
            supabase
            .table("crawler_reviews")
            .select("*")
            .execute()
        )

        rows = response.data or []

        return pd.DataFrame(rows)

    except Exception as exc:
        st.error(
            "Could not load review feedback from the database."
        )
        st.caption(str(exc))
        return pd.DataFrame()


def load_feedback_from_excel() -> pd.DataFrame:
    """
    Loads local Excel feedback as a development fallback.
    """
    if not FEEDBACK_FILE.exists():
        return pd.DataFrame()

    return pd.read_excel(
        FEEDBACK_FILE
    )


def load_feedback_data(
    supabase: Client | None,
) -> pd.DataFrame:
    """
    Loads review feedback.

    Uses Supabase when configured.
    Falls back to the local Excel workbook during local development.
    """
    if supabase is not None:
        return load_feedback_from_supabase(
            supabase
        )

    return load_feedback_from_excel()
def build_feedback_excel_download(
    feedback_df: pd.DataFrame,
) -> bytes:
    """
    Builds an in-memory Excel workbook containing saved review feedback.
    """
    output = BytesIO()

    export_df = feedback_df.copy()

    preferred_columns = [
        "organization",
        "name",
        "title",
        "email",
        "role_category",
        "review_status",
        "reviewer_notes",
        "reviewer_name",
        "reviewed_at",
        "source_url",
    ]

    existing_columns = [
        column
        for column in preferred_columns
        if column in export_df.columns
    ]

    export_df = export_df[
        existing_columns
    ]

    export_df.to_excel(
        output,
        index=False,
        engine="openpyxl",
    )

    output.seek(0)

    return output.getvalue()

def save_contact_review_to_supabase(
    supabase: Client,
    contact: pd.Series,
    review_status: str,
    reviewer_notes: str,
) -> None:
    """
    Saves or updates one contact review in Supabase.
    """
    organization = clean_storage_value(
        contact.get("organization")
    )
    name = clean_storage_value(
        contact.get("name")
    )
    title = clean_storage_value(
        contact.get("title")
    )
    email = clean_storage_value(
        contact.get("email")
    )
    role_category = clean_storage_value(
        contact.get("role_categories")
    )
    source_url = clean_storage_value(
        contact.get("source_url")
    )

    reviewed_at = datetime.now(
        timezone.utc
    ).isoformat()

    review_record = {
        "organization": organization,
        "name": name,
        "title": title,
        "email": email,
        "role_category": role_category,
        "review_status": review_status,
        "reviewer_notes": reviewer_notes.strip(),
        "reviewer_name": REVIEWER_NAME,
        "reviewed_at": reviewed_at,
        "source_url": source_url,
        "updated_at": reviewed_at,
    }

    (
        supabase
        .table("crawler_reviews")
        .upsert(
            review_record,
            on_conflict="organization,name,email",
        )
        .execute()
    )


def save_contact_review_to_excel(
    contact: pd.Series,
    review_status: str,
    reviewer_notes: str,
) -> None:
    """
    Saves or updates one review in the local Excel fallback file.
    """
    ensure_feedback_dir()

    feedback_df = load_feedback_from_excel()

    organization = clean_storage_value(
        contact.get("organization")
    )
    name = clean_storage_value(
        contact.get("name")
    )
    title = clean_storage_value(
        contact.get("title")
    )
    email = clean_storage_value(
        contact.get("email")
    )
    role_categories = clean_storage_value(
        contact.get("role_categories")
    )
    source_url = clean_storage_value(
        contact.get("source_url")
    )

    reviewed_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    new_row = {
        "organization": organization,
        "name": name,
        "title": title,
        "email": email,
        "role_categories": role_categories,
        "review_status": review_status,
        "reviewer_notes": reviewer_notes.strip(),
        "reviewed_at": reviewed_at,
        "source_url": source_url,
    }

    if feedback_df.empty:
        feedback_df = pd.DataFrame(
            [new_row]
        )

    else:
        existing_match = (
            feedback_df["organization"]
            .astype(str)
            .eq(organization)
            & feedback_df["name"]
            .astype(str)
            .eq(name)
            & feedback_df["title"]
            .astype(str)
            .eq(title)
        )

        if existing_match.any():
            first_index = feedback_df[
                existing_match
            ].index[0]

            for column, value in new_row.items():
                feedback_df.at[
                    first_index,
                    column,
                ] = value

        else:
            feedback_df = pd.concat(
                [
                    feedback_df,
                    pd.DataFrame([new_row]),
                ],
                ignore_index=True,
            )

    feedback_df.to_excel(
        FEEDBACK_FILE,
        index=False,
    )


def save_contact_review(
    supabase: Client | None,
    contact: pd.Series,
    review_status: str,
    reviewer_notes: str,
) -> None:
    """
    Saves a review to Supabase when available.

    Falls back to local Excel during local development.
    """
    if supabase is not None:
        save_contact_review_to_supabase(
            supabase=supabase,
            contact=contact,
            review_status=review_status,
            reviewer_notes=reviewer_notes,
        )
        return

    save_contact_review_to_excel(
        contact=contact,
        review_status=review_status,
        reviewer_notes=reviewer_notes,
    )


def get_saved_review(
    contact: pd.Series,
    feedback_df: pd.DataFrame,
) -> dict:
    """
    Returns saved review data for one contact.
    """
    if feedback_df.empty:
        return {
            "review_status": "Not Reviewed",
            "reviewer_notes": "",
        }

    organization = clean_storage_value(
        contact.get("organization")
    )
    name = clean_storage_value(
        contact.get("name")
    )

    matching_rows = feedback_df[
        feedback_df["organization"]
        .astype(str)
        .eq(organization)
        & feedback_df["name"]
        .astype(str)
        .eq(name)
    ]

    email = clean_storage_value(
        contact.get("email")
    )

    if (
        not matching_rows.empty
        and "email" in matching_rows.columns
    ):
        email_matches = matching_rows[
            matching_rows["email"]
            .fillna("")
            .astype(str)
            .eq(email)
        ]

        if not email_matches.empty:
            matching_rows = email_matches

    if matching_rows.empty:
        return {
            "review_status": "Not Reviewed",
            "reviewer_notes": "",
        }

    saved_row = matching_rows.iloc[0]

    saved_status = saved_row.get(
        "review_status",
        "Not Reviewed",
    )

    if pd.isna(saved_status):
        saved_status = "Not Reviewed"

    saved_status = str(
        saved_status
    ).strip()

    if saved_status not in REVIEW_STATUS_OPTIONS:
        saved_status = "Not Reviewed"

    saved_notes = saved_row.get(
        "reviewer_notes",
        "",
    )

    if pd.isna(saved_notes):
        saved_notes = ""

    return {
        "review_status": saved_status,
        "reviewer_notes": str(saved_notes),
    }


def get_review_status_for_contact(
    contact: pd.Series,
    feedback_df: pd.DataFrame,
) -> str:
    """
    Returns only the saved review status.
    """
    saved_review = get_saved_review(
        contact=contact,
        feedback_df=feedback_df,
    )

    return saved_review[
        "review_status"
    ]


def build_contact_key(
    contact: pd.Series,
    index: int,
) -> str:
    """
    Builds a stable Streamlit widget key.
    """
    organization = clean_display_value(
        contact.get("organization")
    )
    name = clean_display_value(
        contact.get("name")
    )

    safe_key = (
        f"{organization}_{name}_{index}"
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )

    return safe_key


def display_contact_card(
    contact: pd.Series,
    index: int,
    feedback_df: pd.DataFrame,
    supabase: Client | None,
) -> None:
    """
    Displays one crawler contact with review controls.
    """
    name = clean_display_value(
        contact.get("name")
    )
    title = clean_display_value(
        contact.get("title")
    )
    department = clean_display_value(
        contact.get("department")
    )
    phone = clean_display_value(
        contact.get("phone")
    )
    email = clean_display_value(
        contact.get("email")
    )

    role_categories = clean_display_value(
        contact.get("role_categories")
    )

    source_type = clean_display_value(
        contact.get("source_type")
    )

    source_page_title = clean_display_value(
        contact.get("source_page_title")
    )

    source_url = clean_display_value(
        contact.get("source_url")
    )

    additional_source_page_titles = clean_display_value(
        contact.get(
            "additional_source_page_titles"
        )
    )

    additional_source_urls = clean_display_value(
        contact.get(
            "additional_source_urls"
        )
    )

    saved_review = get_saved_review(
        contact=contact,
        feedback_df=feedback_df,
    )

    contact_key = build_contact_key(
        contact=contact,
        index=index,
    )

    saved_status = saved_review[
        "review_status"
    ]

    saved_notes = saved_review[
        "reviewer_notes"
    ]

    status_index = REVIEW_STATUS_OPTIONS.index(
        saved_status
    )

    with st.container(
        border=True
    ):
        st.subheader(name)
        st.write(
            f"**{title}**"
        )

        col1, col2 = st.columns(2)

        with col1:
            st.write(
                f"**Department:** {department}"
            )
            st.write(
                f"**Phone:** {phone}"
            )
            st.write(
                f"**Email:** {email}"
            )

        with col2:
            st.write(
                f"**Role Category:** "
                f"{role_categories}"
            )
            st.write(
                f"**Source Type:** "
                f"{source_type}"
            )
            st.write(
                f"**Source Page:** "
                f"{source_page_title}"
            )

        if source_url != "—":
            st.link_button(
                "Open Source Page",
                source_url,
            )

        if (
            additional_source_page_titles != "—"
            or additional_source_urls != "—"
        ):
            with st.expander(
                "Additional Source Information"
            ):
                st.write(
                    "**Additional Source Page:** "
                    f"{additional_source_page_titles}"
                )

                if additional_source_urls != "—":
                    st.write(
                        "**Additional Source URL:** "
                        f"{additional_source_urls}"
                    )

        st.divider()

        st.write(
            "### Adrien's Review"
        )

        review_status = st.radio(
            "Review Status",
            options=REVIEW_STATUS_OPTIONS,
            index=status_index,
            key=f"review_status_{contact_key}",
        )

        reviewer_notes = st.text_area(
            "Reviewer Notes",
            value=saved_notes,
            placeholder=(
                "Add notes about this contact "
                "or the crawler result."
            ),
            key=f"review_notes_{contact_key}",
        )

        if saved_status != "Not Reviewed":
            st.caption(
                f"Previously saved status: "
                f"{saved_status}"
            )

        if st.button(
            "Save Review",
            key=f"save_review_{contact_key}",
        ):
            try:
                save_contact_review(
                    supabase=supabase,
                    contact=contact,
                    review_status=review_status,
                    reviewer_notes=reviewer_notes,
                )

                st.success(
                    "Review saved successfully."
                )

                st.rerun()

            except Exception as exc:
                st.error(
                    "The review could not be saved."
                )
                st.caption(
                    str(exc)
                )


def main():
    st.set_page_config(
        page_title="College Crawler Review",
        page_icon="🎓",
        layout="wide",
    )

    supabase = get_supabase_client()

    st.title(
        "College Crawler Review App"
    )

    st.write(
        "Review College Crawler results "
        "one institution at a time."
    )

    df, latest_file = (
        load_latest_role_target_data()
    )

    if df.empty or latest_file is None:
        st.warning(
            "No role-target Excel export "
            "was found in data/output or data/sample."
        )
        return

    feedback_df = load_feedback_data(
        supabase
    )
    feedback_excel = build_feedback_excel_download(
        feedback_df
    )

    st.download_button(
        label="Download Reviews as Excel",
        data=feedback_excel,
        file_name="crawler_review_feedback.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
    total_saved_reviews = len(feedback_df)

    correct_count = 0
    incorrect_count = 0
    missing_info_count = 0
    manual_review_count = 0

    if not feedback_df.empty and "review_status" in feedback_df.columns:
        correct_count = (
            feedback_df["review_status"]
            .astype(str)
            .eq("Correct")
            .sum()
        )

        incorrect_count = (
            feedback_df["review_status"]
            .astype(str)
            .eq("Incorrect")
            .sum()
        )

        missing_info_count = (
            feedback_df["review_status"]
            .astype(str)
            .eq("Missing Information")
            .sum()
        )

        manual_review_count = (
            feedback_df["review_status"]
            .astype(str)
            .eq("Needs Manual Review")
            .sum()
        )

    st.subheader("Overall Review Summary")

    summary_col1, summary_col2, summary_col3, summary_col4, summary_col5 = st.columns(5)

    with summary_col1:
        st.metric(
            "Total Reviewed",
            total_saved_reviews,
        )

    with summary_col2:
        st.metric(
            "Correct",
            correct_count,
        )

    with summary_col3:
        st.metric(
            "Incorrect",
            incorrect_count,
        )

    with summary_col4:
        st.metric(
            "Missing Information",
            missing_info_count,
        )

    with summary_col5:
        st.metric(
            "Needs Manual Review",
            manual_review_count,
        )

    st.divider()
    st.success(
        f"Loaded {len(df)} contact records "
        "from the latest crawler export."
    )

    st.caption(
        f"Source file: {latest_file.name}"
    )

    if supabase is not None:
        st.caption(
            "Review storage: Supabase database"
        )
    else:
        st.caption(
            "Review storage: Local Excel fallback"
        )

    if "organization" not in df.columns:
        st.error(
            "The crawler export does not "
            "contain an organization column."
        )
        return

    colleges = sorted(
        df["organization"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if not colleges:
        st.warning(
            "No colleges were found "
            "in the crawler export."
        )
        return

    st.divider()

    selected_college = st.selectbox(
        "Select a College",
        options=colleges,
    )

    college_df = df[
        df["organization"]
        == selected_college
    ].copy()

    college_df[
        "saved_review_status"
    ] = college_df.apply(
        lambda row: get_review_status_for_contact(
            contact=row,
            feedback_df=feedback_df,
        ),
        axis=1,
    )

    total_contacts = len(
        college_df
    )

    reviewed_contacts = len(
        college_df[
            college_df[
                "saved_review_status"
            ]
            != "Not Reviewed"
        ]
    )

    remaining_contacts = (
        total_contacts
        - reviewed_contacts
    )

    progress_value = 0.0

    if total_contacts > 0:
        progress_value = (
            reviewed_contacts
            / total_contacts
        )

    st.subheader(
        selected_college
    )

    col1, col2, col3, col4 = st.columns(
        4
    )

    with col1:
        st.metric(
            "Contacts Found",
            total_contacts,
        )

    with col2:
        role_count = 0

        if (
            "role_categories"
            in college_df.columns
        ):
            role_count = (
                college_df[
                    "role_categories"
                ]
                .dropna()
                .nunique()
            )

        st.metric(
            "Role Categories",
            role_count,
        )

    with col3:
        st.metric(
            "Reviewed",
            reviewed_contacts,
        )

    with col4:
        st.metric(
            "Remaining",
            remaining_contacts,
        )

    st.progress(
        progress_value,
        text=(
            f"{reviewed_contacts} of "
            f"{total_contacts} contacts reviewed"
        ),
    )

    st.divider()

    review_filter = st.selectbox(
        "Filter Contacts",
        options=[
            "All Contacts",
            "Not Reviewed",
            "Reviewed",
            "Correct",
            "Incorrect",
            "Wrong Role",
            "Duplicate",
            "Missing Information",
            "Needs Manual Review",
        ],
    )

    filtered_df = college_df.copy()

    if review_filter == "Not Reviewed":
        filtered_df = filtered_df[
            filtered_df[
                "saved_review_status"
            ]
            == "Not Reviewed"
        ]

    elif review_filter == "Reviewed":
        filtered_df = filtered_df[
            filtered_df[
                "saved_review_status"
            ]
            != "Not Reviewed"
        ]

    elif review_filter != "All Contacts":
        filtered_df = filtered_df[
            filtered_df[
                "saved_review_status"
            ]
            == review_filter
        ]

    st.subheader(
        "Contact Review"
    )

    st.caption(
        f"Showing {len(filtered_df)} of "
        f"{total_contacts} contacts."
    )

    if filtered_df.empty:
        st.info(
            "No contacts match "
            "the selected filter."
        )
        return

    for index, (_, contact) in enumerate(
        filtered_df.iterrows()
    ):
        display_contact_card(
            contact=contact,
            index=index,
            feedback_df=feedback_df,
            supabase=supabase,
        )


if __name__ == "__main__":
    main()