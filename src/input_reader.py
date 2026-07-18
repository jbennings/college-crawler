import pandas as pd

from config import INPUT_FILE, INPUT_SHEET_NAME, REQUIRED_COLUMNS


def list_sheet_names():
    excel_file = pd.ExcelFile(INPUT_FILE)
    return excel_file.sheet_names


def find_header_row():
    preview = pd.read_excel(
        INPUT_FILE,
        sheet_name=INPUT_SHEET_NAME,
        header=None,
        nrows=10
    )

    for index, row in preview.iterrows():
        row_values = [str(value).strip() for value in row.values]

        if "Org ID" in row_values and "Organization" in row_values:
            return index

    raise ValueError("Could not find the header row containing 'Org ID' and 'Organization'.")


def clean_dataframe(df):
    df = df.copy()

    df.columns = [str(col).strip() for col in df.columns]

    df = df.dropna(how="all")

    df = df[df["Organization"].notna()]

    text_columns = df.select_dtypes(include=["object"]).columns

    for column in text_columns:
        df[column] = df[column].astype(str).str.strip()
        df[column] = df[column].replace({"nan": ""})

    return df


def validate_columns(df):
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]

    if missing_columns:
        print("\nActual spreadsheet columns:")
        for column in df.columns:
            print(f"- {repr(column)}")

        raise ValueError(f"Missing required columns: {missing_columns}")


def load_input_spreadsheet():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    try:
        header_row = find_header_row()

        df = pd.read_excel(
            INPUT_FILE,
            sheet_name=INPUT_SHEET_NAME,
            header=header_row
        )

    except ValueError as e:
        print("\nAvailable sheet names:")
        for sheet in list_sheet_names():
            print(f"- {repr(sheet)}")
        raise e

    df = clean_dataframe(df)

    validate_columns(df)

    return df

def clean_value(value):
    if pd.isna(value):
        return ""

    return str(value).strip()

def dataframe_to_records(df):
    records = []

    for _, row in df.iterrows():
        record = {
            "org_id": clean_value(row.get("Org ID", "")),
            "organization": clean_value(row.get("Organization", "")),
            "institution_type": clean_value(row.get("Institution Type", "")),
            "district": clean_value(row.get("District", "")),
            "state": clean_value(row.get("State", "")),
            "region": clean_value(row.get("Region", "")),
            "website": clean_value(row.get("Website", "")),
            "board_page": clean_value(row.get("Board Page", "")),
            "chancellor": clean_value(row.get("Chancellor", "")),
            "president_ceo": clean_value(row.get("President/CEO", "")),
            "primary_email": clean_value(row.get("Primary Email", "")),
            "primary_phone": clean_value(row.get("Primary Phone", "")),
            "mailing_address": clean_value(row.get("Mailing Address", "")),
            "strategic_plan": clean_value(row.get("Strategic Plan", "")),
            "last_verified_date": clean_value(row.get("Last Verified Date", "")),
        }

        records.append(record)

    return records