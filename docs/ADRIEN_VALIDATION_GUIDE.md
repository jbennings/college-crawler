# College Crawler Alpha Validation Guide

## Purpose

The purpose of alpha validation is to determine whether the College Crawler consistently identifies the correct executive leadership contacts for each institution.

This is not a test of whether the software is perfect. It is a structured process for identifying extraction patterns, missing information, incorrect classifications, and opportunities to improve the crawler.

## Validator

**Primary Validator:** Adrien  
**Role:** Leadership Data Validator

The validator should focus on the accuracy and completeness of the contact information rather than the underlying code.

---

## Validation Workflow

For each college:

1. Select the institution in the College Crawler Review App.
2. Review each contact extracted by the crawler.
3. Open the source webpage when verification is needed.
4. Compare the extracted record with the institution’s current website.
5. Assign the appropriate review status.
6. Add a brief note when the record is not fully correct.
7. Save the review.
8. Continue until all displayed contacts for the institution have been reviewed.
9. Determine whether any expected leadership contacts are missing.

---

## Review Status Definitions

### Not Reviewed

The contact has not yet been evaluated.

### Correct

Use when all relevant information is accurate:

- Name
- Title
- Role category
- Email address, when available
- Phone number, when available
- Department, when available

### Incorrect

Use when the contact should be included, but one or more important details are inaccurate.

The reviewer note should identify what is incorrect.

Example:

> Correct person, but the title should be Vice President for Student Affairs.

### Wrong Role

Use when the person is real, but should not be included in the target leadership group or has been placed in the wrong role category.

Example:

> Executive Director was classified as a Vice President.

### Duplicate

Use when the same person appears more than once in the crawler results.

The reviewer note should identify the other duplicate record when possible.

### Missing Information

Use when the person is correct, but important information is absent.

Examples:

- Missing email address
- Missing phone number
- Incomplete title
- Missing department

### Needs Manual Review

Use when the reviewer cannot confidently determine whether the record is correct.

Examples:

- Conflicting information appears on different pages.
- The institution’s website appears outdated.
- The leadership role is unclear.
- The source page is unavailable.

---

## Institution-Level Validation Questions

After reviewing all extracted contacts for an institution, determine:

### President or Chancellor

- Was the current President or Chancellor identified?
- Is the name correct?
- Is the title correct?
- Is the contact information correct?

### Executive Assistant

- Was the President’s or Chancellor’s Executive Assistant identified?
- Was an unrelated administrative assistant included instead?
- Is the assistant’s title and contact information correct?

### Senior Leadership

- Were the appropriate cabinet or executive leadership members identified?
- Were Vice Presidents included?
- Were senior leaders omitted?
- Were lower-level employees incorrectly included?

### Data Quality

- Are email addresses accurate?
- Are phone numbers accurate?
- Are departments accurate?
- Are titles current?
- Are any contacts duplicated?

### Completeness

- Is anyone clearly missing from the institution’s executive leadership page?
- Did the crawler overlook a separate cabinet, administration, or leadership page?
- Are relevant contacts listed on another official institutional page?

---

## Reviewer Note Standards

Notes should be brief, specific, and actionable.

### Good Notes

> President is correct, but the email address is missing.

> This person is the Executive Director of Marketing and should not be classified as a Vice President.

> Current cabinet page lists six members; the crawler extracted only four.

> Duplicate of the Susan Thomas record shown above.

### Avoid

> Wrong.

> Fix this.

> Looks strange.

> Not sure.

When uncertain, explain what caused the uncertainty.

---

## Recommended Validation Order

Validate institutions in manageable batches.

### Initial Pilot

Review the first 5 institutions completely.

The purpose of this pilot is to confirm that:

- The review controls work correctly.
- Saved reviews remain available.
- Reviewer notes are captured.
- Source links open correctly.
- The available status options are sufficient.

### Alpha Batch 1

Review 10 institutions.

After this batch, identify recurring issues such as:

- Missing Executive Assistants
- Incorrect role classifications
- Missing cabinet members
- Duplicate contacts
- Incorrect or missing contact information

### Alpha Batch 2

Review the remaining institutions in the state dataset.

After completion, calculate overall accuracy and identify the highest-priority crawler improvements.

---

## Initial Success Measures

The alpha release will be evaluated using the following targets:

| Measure | Initial Target |
|---|---:|
| President or Chancellor identified | 98% or higher |
| Executive Assistant identified | 90% or higher |
| Target senior leaders identified | 90% or higher |
| Email accuracy | 95% or higher |
| Duplicate rate | Less than 2% |
| False-positive rate | Less than 5% |

These are improvement targets rather than guarantees for the first validation cycle.

---

## Issue Escalation

Stop reviewing an institution and mark the relevant contacts as **Needs Manual Review** when:

- The source website is unavailable.
- Multiple official pages contain conflicting information.
- The institution appears to be undergoing a leadership transition.
- The review app does not save the review.
- A technical error prevents the institution from being reviewed.

Record a clear note describing the issue.

---

## Completion Standard

An institution is considered reviewed when:

- Every extracted contact has a saved review status.
- Incorrect or incomplete records contain reviewer notes.
- The President or Chancellor has been verified.
- The Executive Assistant has been checked.
- The institution’s executive or cabinet page has been checked for missing leaders.
- Any institution-level concerns have been documented.

---

## Validation Cycle

The continuous-improvement process is:

**Crawl → Review → Analyze → Improve → Re-Crawl**

Each validation cycle should result in:

1. A reviewed dataset.
2. A summary of recurring issues.
3. A prioritized list of crawler improvements.
4. A new crawler version.
5. A new validation batch.