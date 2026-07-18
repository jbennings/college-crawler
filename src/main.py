from crawler import (
    check_websites,
    discover_pages_for_records,
    flatten_discovered_pages,
    summarize_extraction_readiness,
)
from exporter import export_role_target_contacts
from extractor import (
    fetch_html_page_texts,
    fetch_html_page_texts_balanced_by_organization,
    extract_basic_contacts_from_fetched_pages,
    summarize_basic_contact_extraction,
    extract_structured_directory_contacts_from_fetched_pages,
    summarize_structured_directory_contacts,
    extract_leadership_contacts_from_fetched_pages,
    summarize_leadership_contacts,
    merge_duplicate_contacts_across_sources,
    classify_role_targets_from_contacts,
    filter_role_target_contacts,
    summarize_role_target_contacts,
)
from input_reader import load_input_spreadsheet, dataframe_to_records


def show_menu():
    print("\nCollege Crawler")
    print("----------------")
    print("1. Load input spreadsheet")
    print("2. Check official websites")
    print("3. Discover useful pages")
    print("4. Find board pages")
    print("5. Find strategic plans")
    print("6. Run full crawl")
    print("0. Exit")


def ask_record_limit(default_limit: int = 5) -> int:
    """
    Asks the user how many records to test.

    If the user presses Enter, the default limit is used.
    If the user types something invalid, the default limit is used.
    """
    user_input = input(
        f"How many records do you want to test? "
        f"Press Enter for {default_limit}: "
    ).strip()

    if not user_input:
        return default_limit

    try:
        limit = int(user_input)

        if limit <= 0:
            print(f"Invalid number. Using default: {default_limit}")
            return default_limit

        return limit

    except ValueError:
        print(f"Invalid number. Using default: {default_limit}")
        return default_limit


def ask_yes_no(prompt: str, default: str = "n") -> bool:
    """
    Simple yes/no prompt.

    default:
        'y' or 'n'
    """
    default = default.lower().strip()

    if default not in ("y", "n"):
        default = "n"

    suffix = "Y/n" if default == "y" else "y/N"

    user_input = input(f"{prompt} ({suffix}): ").strip().lower()

    if not user_input:
        return default == "y"

    return user_input in ("y", "yes")


def print_discovered_pages(results: list[dict]):
    """
    Prints discovered page results grouped by organization and category.
    """
    for result in results:
        print("\n================================")
        print(f"Organization: {result['organization']}")
        print(f"Website: {result['website']}")

        categories = result["categories"]

        if not categories:
            print("No useful pages discovered.")
            continue

        for category, links in categories.items():
            print(f"\n--- {category.upper()} ---")

            if not links:
                continue

            for link in links:
                print(f"\n  Score: {link['score']}")
                print(f"  Link Text: {link['text']}")
                print(f"  URL: {link['url']}")
                print(f"  Source: {link['source']}")
                print("  Reasons:")

                for reason in link["reasons"]:
                    print(f"    - {reason}")


def print_extraction_ready_pages(flattened_pages: list[dict]):
    """
    Prints a compact extraction-ready page list.

    This is not extraction yet. It only shows what pages would be sent
    to the future extractor.
    """
    print("\n\n================================")
    print("EXTRACTION-READY PAGE RECORDS")
    print("================================")

    if not flattened_pages:
        print("No extraction-ready pages found.")
        return

    current_org = None

    for page in flattened_pages:
        organization = page.get("organization", "")

        if organization != current_org:
            current_org = organization
            print("\n--------------------------------")
            print(f"Organization: {organization}")
            print("--------------------------------")

        review_marker = "REVIEW" if page.get("needs_review") else "OK"

        print(
            f"[{review_marker}] "
            f"{page.get('category', '').upper()} | "
            f"Score {page.get('score', 0)} | "
            f"{page.get('page_title', '')}"
        )
        print(f"    URL: {page.get('url', '')}")
        print(f"    Source: {page.get('source', '')}")

        validation_status = page.get("validation_status", "")

        if validation_status:
            print(f"    Validation: {validation_status}")

        if page.get("needs_review"):
            validation_reason = page.get("validation_reason", "")

            if validation_reason:
                print(f"    Review Reason: {validation_reason}")


def print_extraction_summary(summary: dict):
    """
    Prints a compact summary of extraction readiness.
    """
    print("\n\n================================")
    print("EXTRACTION READINESS SUMMARY")
    print("================================")

    print(f"Total extraction-ready pages: {summary.get('total_pages', 0)}")
    print(f"Pages needing review: {summary.get('needs_review', 0)}")

    print("\nBy category:")

    by_category = summary.get("by_category", {})

    if not by_category:
        print("  No categories found.")
        return

    for category, values in by_category.items():
        print(
            f"  {category}: "
            f"{values.get('total', 0)} total, "
            f"{values.get('needs_review', 0)} needing review"
        )


def print_fetched_page_text_results(results: list[dict]):
    """
    Prints a compact preview of fetched page text results.
    """
    print("\n\n================================")
    print("FETCHED PAGE TEXT RESULTS")
    print("================================")

    if not results:
        print("No pages were fetched.")
        return

    for result in results:
        print("\n--------------------------------")
        print(f"Organization: {result.get('organization', '')}")
        print(f"Category: {result.get('category', '')}")
        print(f"Source Page: {result.get('source_page_title', '')}")
        print(f"URL: {result.get('url', '')}")
        print(f"Status: {result.get('status', '')}")
        print(f"Status Code: {result.get('status_code', '')}")
        print(f"Content Type: {result.get('content_type', '')}")
        print(f"Fetched Title: {result.get('title', '')}")
        print(f"Text Length: {result.get('text_length', 0)}")

        if result.get("error"):
            print(f"Error: {result.get('error')}")

        text = result.get("text", "")

        if text:
            preview = text[:700]

            print("\nText Preview:")
            print(preview)

            if len(text) > len(preview):
                print("...")


def print_basic_contact_summary(summary: dict):
    """
    Prints a compact summary of basic contact extraction.
    """
    print("\n\n================================")
    print("BASIC CONTACT EXTRACTION SUMMARY")
    print("================================")

    print(f"Pages processed: {summary.get('pages_processed', 0)}")
    print(f"Pages with emails: {summary.get('pages_with_emails', 0)}")
    print(f"Pages with phones: {summary.get('pages_with_phones', 0)}")
    print(f"Total emails found: {summary.get('total_emails', 0)}")
    print(f"Total phones found: {summary.get('total_phones', 0)}")


def print_basic_contact_results(results: list[dict]):
    """
    Prints basic extracted emails and phone numbers.
    """
    print("\n\n================================")
    print("BASIC CONTACT EXTRACTION RESULTS")
    print("================================")

    if not results:
        print("No basic contacts extracted.")
        return

    for result in results:
        print("\n--------------------------------")
        print(f"Organization: {result.get('organization', '')}")
        print(f"Category: {result.get('category', '')}")
        print(f"Source Page: {result.get('source_page_title', '')}")
        print(f"URL: {result.get('url', '')}")
        print(f"Fetched Title: {result.get('fetched_title', '')}")
        print(f"Text Length: {result.get('text_length', 0)}")
        print(f"Email Count: {result.get('email_count', 0)}")
        print(f"Phone Count: {result.get('phone_count', 0)}")

        emails = result.get("emails", [])
        phones = result.get("phones", [])

        if emails:
            print("\nEmails:")

            for email in emails[:20]:
                print(f"  - {email}")

            if len(emails) > 20:
                print(f"  ... and {len(emails) - 20} more")

        if phones:
            print("\nPhones:")

            for phone in phones[:20]:
                print(f"  - {phone}")

            if len(phones) > 20:
                print(f"  ... and {len(phones) - 20} more")


def print_structured_directory_contact_summary(summary: dict):
    """
    Prints a compact summary of structured directory contact extraction.
    """
    print("\n\n================================")
    print("STRUCTURED DIRECTORY CONTACT SUMMARY")
    print("================================")

    print(f"Total contacts: {summary.get('total_contacts', 0)}")
    print(f"Contacts with name: {summary.get('contacts_with_name', 0)}")
    print(f"Contacts with title: {summary.get('contacts_with_title', 0)}")
    print(
        f"Contacts with department: "
        f"{summary.get('contacts_with_department', 0)}"
    )
    print(f"Contacts with phone: {summary.get('contacts_with_phone', 0)}")
    print(f"Contacts with email: {summary.get('contacts_with_email', 0)}")


def print_structured_directory_contacts(contacts: list[dict]):
    """
    Prints a sample of structured directory contact records.
    """
    print("\n\n================================")
    print("STRUCTURED DIRECTORY CONTACT RESULTS")
    print("================================")

    if not contacts:
        print("No structured directory contacts found.")
        return

    for contact in contacts[:25]:
        print("\n--------------------------------")
        print(f"Organization: {contact.get('organization', '')}")
        print(f"Name: {contact.get('name', '')}")
        print(f"Title: {contact.get('title', '')}")
        print(f"Department: {contact.get('department', '')}")
        print(f"Phone: {contact.get('phone', '')}")
        print(f"Email: {contact.get('email', '')}")
        print(f"Source Page: {contact.get('source_page_title', '')}")
        print(f"Source URL: {contact.get('source_url', '')}")

    if len(contacts) > 25:
        print(f"\n... and {len(contacts) - 25} more structured contacts")


def print_combined_contact_summary(
    structured_contacts: list[dict],
    leadership_contacts: list[dict],
    merged_contacts: list[dict],
):
    """
    Prints counts before and after cross-source contact merging.
    """
    unmerged_count = len(structured_contacts) + len(leadership_contacts)

    print("\n\n================================")
    print("COMBINED CONTACT RECORDS")
    print("================================")

    print(f"Structured directory contacts: {len(structured_contacts)}")
    print(f"Leadership-page contacts: {len(leadership_contacts)}")
    print(f"Combined contacts before merging: {unmerged_count}")
    print(f"Contacts after cross-source merging: {len(merged_contacts)}")
    print(f"Duplicate records merged: {unmerged_count - len(merged_contacts)}")


def print_role_target_summary(summary: dict):
    """
    Prints role-target contact summary.
    """
    print("\n\n================================")
    print("ROLE-TARGET CONTACT SUMMARY")
    print("================================")

    print(f"Total role targets: {summary.get('total_role_targets', 0)}")

    by_role_category = summary.get("by_role_category", {})

    if not by_role_category:
        print("No role-target categories found.")
        return

    print("\nBy role category:")

    for category, count in by_role_category.items():
        print(f"  {category}: {count}")


def print_role_target_contacts(role_targets: list[dict]):
    """
    Prints likely high-value outreach contacts.
    """
    print("\n\n================================")
    print("ROLE-TARGET CONTACT RESULTS")
    print("================================")

    if not role_targets:
        print("No role-target contacts found.")
        return

    for contact in role_targets[:50]:
        print("\n--------------------------------")
        print(f"Organization: {contact.get('organization', '')}")
        print(f"Name: {contact.get('name', '')}")
        print(f"Title: {contact.get('title', '')}")
        print(f"Department: {contact.get('department', '')}")
        print(f"Phone: {contact.get('phone', '')}")
        print(f"Email: {contact.get('email', '')}")
        print(
            f"Role Categories: "
            f"{', '.join(contact.get('role_categories', []))}"
        )
        print(
            f"Matched Terms: "
            f"{', '.join(contact.get('matched_role_terms', []))}"
        )
        print(
            f"Priority Score: "
            f"{contact.get('role_priority_score', 0)}"
        )
        print(
            f"Source Type: "
            f"{contact.get('source_type', '')}"
        )
        print(
            f"Source Page: "
            f"{contact.get('source_page_title', '')}"
        )
        print(f"Source URL: {contact.get('source_url', '')}")

        additional_source_types = contact.get(
            "additional_source_types",
            [],
        )
        additional_source_titles = contact.get(
            "additional_source_page_titles",
            [],
        )
        additional_source_urls = contact.get(
            "additional_source_urls",
            [],
        )

        if additional_source_types:
            print(
                "Additional Source Types: "
                f"{', '.join(additional_source_types)}"
            )

        if additional_source_titles:
            print(
                "Additional Source Pages: "
                f"{', '.join(additional_source_titles)}"
            )

        if additional_source_urls:
            print("Additional Source URLs:")

            for source_url in additional_source_urls:
                print(f"  - {source_url}")

    if len(role_targets) > 50:
        print(
            f"\n... and {len(role_targets) - 50} "
            "more role-target contacts"
        )


def print_export_results(export_result: dict):
    """
    Prints export result details.
    """
    print("\n\n================================")
    print("EXPORT RESULTS")
    print("================================")

    print(f"Contacts exported: {export_result.get('count', 0)}")
    print(f"CSV file: {export_result.get('csv_path', '')}")
    print(f"Excel file: {export_result.get('excel_path', '')}")


def main():
    while True:
        show_menu()
        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            try:
                df = load_input_spreadsheet()
                records = dataframe_to_records(df)

                print("Spreadsheet loaded successfully.")
                print(f"Rows found after cleaning: {len(df)}")
                print(f"Records prepared: {len(records)}")

                if records:
                    print("\nFirst record preview:")
                    print(records[0])
                else:
                    print("\nNo records found.")

            except Exception as e:
                print(f"Error loading spreadsheet: {e}")

        elif choice == "2":
            try:
                limit = ask_record_limit(default_limit=10)

                df = load_input_spreadsheet()
                records = dataframe_to_records(df)

                print(f"Checking websites for first {limit} records...")
                results = check_websites(records, limit=limit)

                for result in results:
                    print("\n----------------")
                    print(f"Organization: {result['organization']}")
                    print(f"URL: {result['website']}")
                    print(f"Status: {result['status']}")
                    print(f"Status Code: {result['status_code']}")
                    print(f"Final URL: {result['final_url']}")

                    if result["error"]:
                        print(f"Error: {result['error']}")

            except Exception as e:
                print(f"Error checking websites: {e}")

        elif choice == "3":
            try:
                limit = ask_record_limit(default_limit=5)

                show_extraction_ready = ask_yes_no(
                    "Show extraction-ready page records after grouped output?",
                    default="y",
                )

                test_page_fetching = ask_yes_no(
                    "Fetch sample HTML page text after extraction-ready output?",
                    default="n",
                )

                test_basic_contact_extraction = False

                if test_page_fetching:
                    test_basic_contact_extraction = ask_yes_no(
                        "Run basic email/phone extraction on fetched pages?",
                        default="y",
                    )

                df = load_input_spreadsheet()
                records = dataframe_to_records(df)

                print(
                    "Discovering and ranking useful pages "
                    f"for first {limit} records..."
                )

                records_to_process = records[:limit]

                results = discover_pages_for_records(
                    records_to_process,
                    limit=limit,
                )

                print_discovered_pages(results)

                flattened_pages = flatten_discovered_pages(
                    results=results,
                    original_records=records_to_process,
                )

                summary = summarize_extraction_readiness(flattened_pages)
                print_extraction_summary(summary)

                if show_extraction_ready:
                    print_extraction_ready_pages(flattened_pages)

                if test_page_fetching:
                    fetched_results = (
                        fetch_html_page_texts_balanced_by_organization(
                            page_records=flattened_pages,
                            pages_per_organization=3,
                            max_total_fetched=25,
                            skip_review_pages=True,
                            allowed_categories=(
                                "directory",
                                "leadership",
                                "board",
                            ),
                        )
                    )

                    print_fetched_page_text_results(fetched_results)

                    if test_basic_contact_extraction:
                        contact_results = (
                            extract_basic_contacts_from_fetched_pages(
                                fetched_results
                            )
                        )

                        contact_summary = (
                            summarize_basic_contact_extraction(
                                contact_results
                            )
                        )

                        print_basic_contact_summary(contact_summary)
                        print_basic_contact_results(contact_results)

                    structured_contacts = (
                        extract_structured_directory_contacts_from_fetched_pages(
                            fetched_results
                        )
                    )

                    structured_summary = (
                        summarize_structured_directory_contacts(
                            structured_contacts
                        )
                    )

                    print_structured_directory_contact_summary(
                        structured_summary
                    )
                    print_structured_directory_contacts(
                        structured_contacts
                    )

                    leadership_contacts = (
                        extract_leadership_contacts_from_fetched_pages(
                            fetched_results
                        )
                    )

                    summarize_leadership_contacts(
                        leadership_contacts
                    )

                    unmerged_contacts = (
                        structured_contacts
                        + leadership_contacts
                    )

                    combined_contacts = (
                        merge_duplicate_contacts_across_sources(
                            unmerged_contacts
                        )
                    )

                    print_combined_contact_summary(
                        structured_contacts=structured_contacts,
                        leadership_contacts=leadership_contacts,
                        merged_contacts=combined_contacts,
                    )

                    classified_contacts = (
                        classify_role_targets_from_contacts(
                            combined_contacts
                        )
                    )

                    role_targets = filter_role_target_contacts(
                        classified_contacts
                    )

                    role_target_summary = (
                        summarize_role_target_contacts(
                            role_targets
                        )
                    )

                    print_role_target_summary(role_target_summary)
                    print_role_target_contacts(role_targets)

                    export_result = export_role_target_contacts(
                        role_targets
                    )

                    print_export_results(export_result)

            except Exception as e:
                print(f"Error discovering pages: {e}")

        elif choice == "4":
            print("Finding board pages...")
            print("This option is not built yet. Use option 3 for now.")

        elif choice == "5":
            print("Finding strategic plans...")
            print("This option is not built yet. Use option 3 for now.")

        elif choice == "6":
            print("Running full crawl...")
            print("This option is not built yet. Use option 3 for now.")

        elif choice == "0":
            print("Exiting College Crawler.")
            break

        else:
            print("Invalid choice. Please select 0-6.")


if __name__ == "__main__":
    main()