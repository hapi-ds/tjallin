# Implementation Plan: Integrated Mail and Reporting

## Overview

This plan transforms the tjallin mail service into a self-contained system with SMTP local delivery and IMAP access, and extends the reporting pipeline with cross-linked navigation and journal reports. Implementation proceeds bottom-up: pure Python modules first (testable in isolation), then shell scripts and Docker configuration, then integration wiring.

## Tasks

- [x] 1. Implement mail user parsing module
  - [x] 1.1 Create `src/tj_utils/parse_mail_users.py` with `MailUser`, `ParseResult` dataclasses and `parse_mail_users()` function
    - Implement parsing of comma-separated `user:password` format
    - Validate username (1–64 chars, alphanumeric plus `-_.`) and password (1–128 chars, no commas/colons)
    - Maximum 50 entries enforcement
    - Skip malformed entries with error messages in `ParseResult.errors`
    - Fallback to `TJ_MAIL_SENDER` local-part when value is None/empty
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 1.2 Write property test for mail user parsing
    - **Property 8: TJ_MAIL_USERS parsing correctness**
    - **Validates: Requirements 3.1, 3.2, 3.4**
    - Create `tests/property/test_parse_mail_users_property.py`
    - Generate random mixes of valid and malformed `user:password` entries
    - Assert: valid users + errors == total entry count
    - Assert: all valid entries produce MailUser objects with correct fields

  - [x] 1.3 Write unit tests for mail user parsing
    - Create `tests/unit/test_parse_mail_users.py`
    - Test edge cases: empty input, single user, max 50 users, 51st user rejected
    - Test default fallback from `TJ_MAIL_SENDER` (e.g., `alice@example.com` → username `alice`)
    - Test delimiter edge cases in passwords
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 2. Implement report post-processor module
  - [x] 2.1 Create `src/tj_utils/report_postprocess.py` with `ReportInfo` dataclass and `discover_reports()` function
    - Scan a directory for `.html` files
    - Extract titles from `<title>` or first `<h1>` element
    - Fall back to filename (without extension) when title cannot be parsed
    - _Requirements: 5.1, 5.4, 5.5_

  - [x] 2.2 Implement `generate_nav_header()` and `generate_index()` functions in `src/tj_utils/report_postprocess.py`
    - Generate HTML navigation header with relative links to all reports
    - Mark active report link with CSS class `nav-active`
    - Include link to admin panel using relative path parameter
    - Generate `index.html` listing all reports with titles and links
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

  - [x] 2.3 Implement `inject_nav_headers()` entry point in `src/tj_utils/report_postprocess.py`
    - Orchestrate discover → generate nav → inject into each report after `<body>` tag
    - Generate Report_Index page
    - Return count of processed reports
    - Handle error cases: missing directory, unwritable files
    - _Requirements: 5.1, 5.5, 5.7_

  - [x] 2.4 Write property tests for navigation header completeness
    - **Property 9: Navigation header completeness**
    - **Validates: Requirements 5.1, 5.5**
    - Create `tests/property/test_nav_header_property.py`
    - Generate random sets of report filenames/titles
    - Assert: every report's nav header contains links to all other reports and to the index

  - [x] 2.5 Write property tests for relative links and active styling
    - **Property 10: Navigation links are relative with active styling**
    - **Validates: Requirements 5.2, 5.3**
    - Add to `tests/property/test_nav_header_property.py`
    - Assert: all href values have no leading `/` or protocol prefix
    - Assert: exactly one link has class `nav-active` matching the active filename

  - [x] 2.6 Write property test for report index completeness
    - **Property 11: Report index completeness**
    - **Validates: Requirements 5.4**
    - Create `tests/property/test_report_index_property.py`
    - Generate random report sets, verify index contains entry for each with title and relative link

  - [x] 2.7 Write unit tests for report post-processor
    - Create `tests/unit/test_report_postprocess.py`
    - Test HTML injection positioning (after `<body>` tag)
    - Test title extraction from `<title>` and `<h1>`
    - Test admin link presence in nav header
    - Test empty report directory produces empty index
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add journal report definition
  - [x] 4.1 Add journal report to `project/includes/reports.tji`
    - Add `taskreport JournalReport` definition with `journalmode journal`
    - Include columns: name, journal
    - Configure `journalattributes headline, author, date, summary`
    - Set `sortjournals date.down`
    - Use `hidetask ~hasjournal()` to hide tasks without entries
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 4.2 Write property tests for journal entry rendering and sort order
    - **Property 12: Journal entry rendering completeness**
    - **Property 13: Journal entry sort order**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
    - Create `tests/property/test_journal_report_property.py`
    - Note: These properties validate TJ3 output behavior; test via post-processor integration or mock TJ output

  - [x] 4.3 Write unit tests for journal report
    - Create `tests/unit/test_journal_report.py`
    - Test that journal report definition is syntactically valid TJ3
    - Test empty journal entries message scenario
    - _Requirements: 6.1, 6.6_

- [x] 5. Update compilation script to invoke post-processor
  - [x] 5.1 Modify `services/tj-core/scripts/compile.sh` to call `report_postprocess.py` after successful TJ3 compilation
    - Add `python3 /app/src/report_postprocess.py "$REPORT_DIR"` after successful tj3 run
    - Log post-processing result (number of reports processed)
    - Handle post-processor failure gracefully (log error but don't fail the compile)
    - _Requirements: 5.1, 5.5_

  - [x] 5.2 Update `services/tj-core/Dockerfile` to include Python and the `src/tj_utils` package
    - Add Python 3 to the tj-core container
    - Copy `src/tj_utils/report_postprocess.py` into the container
    - _Requirements: 5.1_

- [x] 6. Implement mail user provisioning and Dovecot configuration
  - [x] 6.1 Create `services/tj-mail/scripts/provision-users.sh`
    - Parse `TJ_MAIL_USERS` environment variable (comma-separated `user:password` pairs)
    - Create system accounts with Maildir directories (`/var/mail/<user>/Maildir/{new,cur,tmp}`)
    - Generate Dovecot passwd-file at `/etc/dovecot/users`
    - Handle fallback to `TJ_MAIL_SENDER` local-part when `TJ_MAIL_USERS` is unset
    - Skip malformed entries with error logging
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 6.2 Create `services/tj-mail/dovecot.conf` with minimal IMAP configuration
    - Protocol: IMAP only (no POP3)
    - Auth: passwd-file at `/etc/dovecot/users`
    - Mail location: `maildir:/var/mail/%u/Maildir`
    - Listen on all interfaces, port 143
    - SSL disabled (internal Docker network)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 7. Rewrite mail service entrypoint and Dockerfile
  - [x] 7.1 Rewrite `services/tj-mail/entrypoint.sh` to remove external relay dependency
    - Remove requirement for `TJ_SMTP_HOST`, `TJ_SMTP_PORT`, `TJ_SMTP_USER`, `TJ_SMTP_PASSWORD`
    - Validate only `TJ_MAIL_DOMAIN` as required (fatal if missing)
    - Configure Postfix for local-only delivery by default
    - Add optional relay support via `TJ_SMTP_RELAY_HOST` and `TJ_SMTP_RELAY_PORT`
    - Call `provision-users.sh` during startup
    - Start both Postfix and Dovecot (use supervisord or sequential start)
    - Configure Postfix `mydestination` to include `TJ_MAIL_DOMAIN`
    - Set `local_transport = local` for Maildir delivery to `/var/mail/<user>/Maildir/`
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 7.2 Update `services/tj-mail/Dockerfile` to install Dovecot and Python
    - Add `dovecot` and `dovecot-imapd` packages
    - Add Python 3 for the provisioning helper
    - Copy `dovecot.conf` into container
    - Copy `provision-users.sh` into container
    - Expose IMAP port 143 in addition to SMTP port 25
    - _Requirements: 2.1, 2.7_

- [x] 8. Update Docker Compose and environment configuration
  - [x] 8.1 Update `docker-compose.yml` for mail service changes
    - Add IMAP port mapping: `127.0.0.1:${TJ_IMAP_PORT:-1143}:143`
    - Add `maildir-data` named volume mounted at `/var/mail`
    - Keep existing `mail-spool` volume for Postfix queue
    - Add `maildir-data` to the volumes section
    - _Requirements: 7.1, 7.2, 7.3, 8.1, 8.2, 8.3, 8.4_

  - [x] 8.2 Update `.env.example` with new environment variables
    - Remove `TJ_SMTP_HOST`, `TJ_SMTP_PORT`, `TJ_SMTP_USER`, `TJ_SMTP_PASSWORD`
    - Add `TJ_MAIL_USERS` with example format
    - Add `TJ_IMAP_PORT` with default 1143
    - Add `TJ_SMTP_RELAY_HOST` and `TJ_SMTP_RELAY_PORT` as optional
    - _Requirements: 3.1, 4.1, 4.3, 7.1_

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Write integration tests
  - [x] 10.1 Write integration tests for mail delivery and IMAP access
    - Create `tests/integration/test_mail_delivery.py` — send email via SMTP, verify Maildir delivery
    - Create `tests/integration/test_imap_access.py` — connect via IMAP, authenticate, list folders, fetch message
    - Create `tests/integration/test_smtp_rejection.py` — non-local domain (554), unknown user (550), oversized (552)
    - _Requirements: 1.2, 1.4, 1.5, 1.6, 1.7, 2.2, 2.3, 2.5, 2.6_

  - [x] 10.2 Write integration tests for mail persistence and startup
    - Create `tests/integration/test_mail_persistence.py` — deliver message, restart container, verify persistence
    - Create `tests/integration/test_startup_no_relay.py` — start without relay variables, verify service accepts connections
    - _Requirements: 4.1, 4.2, 8.1, 8.2, 8.4_

  - [x] 10.3 Write integration test for report navigation
    - Create `tests/integration/test_report_navigation.py` — compile project, verify navigation headers in output HTML
    - Verify journal report is included in navigation
    - _Requirements: 5.1, 5.4, 5.5, 6.5_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Integration tests require a running Docker stack (marked with `@pytest.mark.integration`)
- The project uses `uv` for dependency management and `pytest` with `hypothesis` for testing
- Python modules follow the existing `src/tj_utils/` package layout

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "4.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.2", "4.2", "4.3"] },
    { "id": 2, "tasks": ["2.3", "6.1", "6.2"] },
    { "id": 3, "tasks": ["2.4", "2.5", "2.6", "2.7", "7.1", "7.2"] },
    { "id": 4, "tasks": ["5.1", "5.2", "8.1", "8.2"] },
    { "id": 5, "tasks": ["10.1", "10.2", "10.3"] }
  ]
}
```
