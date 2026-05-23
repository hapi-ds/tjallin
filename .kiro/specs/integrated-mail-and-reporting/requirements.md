# Requirements Document

## Introduction

This feature enhances the tjallin Docker Compose stack in two areas:

1. **Integrated Mail System** — Replace the dependency on an external SMTP relay with a self-contained mail service that provides both SMTP (send/receive within the stack) and IMAP (allowing users to read mail with standard clients). The external relay environment variables (TJ_SMTP_HOST, TJ_SMTP_PORT, TJ_SMTP_USER, TJ_SMTP_PASSWORD) are eliminated.

2. **Enhanced Reporting** — Extend the TaskJuggler reporting system with cross-linked reports (reports containing navigable links to each other) and journaling reports (status/journal entries visible in report output).

## Glossary

- **Mail_Service**: The Docker container (tj-mail) responsible for sending, receiving, and storing email within the tjallin stack.
- **SMTP_Server**: The Simple Mail Transfer Protocol component within the Mail_Service that accepts and delivers messages locally.
- **IMAP_Server**: The Internet Message Access Protocol component within the Mail_Service that allows mail clients to connect and read stored messages.
- **Mail_Client**: Any standard email client (e.g., Thunderbird, Apple Mail) that connects via IMAP to read messages.
- **Report_Generator**: The TaskJuggler compilation process (tj-core) that produces HTML report files from project definitions.
- **Report_Server**: The web service (tj-web) that serves generated HTML reports to browsers.
- **Cross_Link**: A navigable HTML hyperlink within a report that points to another report in the same set.
- **Journal_Report**: A report type that displays status and journal entries recorded against tasks or the project.
- **Report_Index**: An HTML page listing all available reports with links, serving as a navigation hub.
- **Maildir**: A standard mailbox format where each message is stored as a separate file in a directory hierarchy (new/, cur/, tmp/).
- **Docker_Network**: The internal bridge network (tj-net) connecting all services in the stack.

## Requirements

### Requirement 1: Self-Contained SMTP Server

**User Story:** As a stack operator, I want the mail service to send and receive email without an external SMTP relay, so that the stack is fully self-contained and requires no third-party mail credentials.

#### Acceptance Criteria

1. THE Mail_Service SHALL provide an SMTP server that accepts messages on port 25 within the Docker_Network.
2. WHEN a service within the Docker_Network sends an email to a local domain address, THE SMTP_Server SHALL deliver the message to the recipient's Maildir without requiring external relay configuration.
3. WHEN the Mail_Service starts, THE SMTP_Server SHALL begin accepting connections within 30 seconds.
4. THE Mail_Service SHALL deliver messages addressed to any user at the configured TJ_MAIL_DOMAIN to local Maildir storage.
5. IF a message is addressed to a domain other than TJ_MAIL_DOMAIN, THEN THE SMTP_Server SHALL reject the message with SMTP reply code 554.
6. IF a message is addressed to a user that does not exist at TJ_MAIL_DOMAIN, THEN THE SMTP_Server SHALL reject the message with SMTP reply code 550.
7. THE SMTP_Server SHALL reject messages larger than 5,242,880 bytes (5 MB) with SMTP reply code 552.
8. IF the SMTP_Server cannot write a delivered message to the recipient's Maildir, THEN THE SMTP_Server SHALL respond with a temporary failure code (SMTP 451) and retain the message in the mail queue for retry.

### Requirement 2: IMAP Access for Mail Clients

**User Story:** As a project team member, I want to connect a standard mail client to the stack via IMAP, so that I can read timesheet reminders and system notifications in my preferred email application.

#### Acceptance Criteria

1. THE Mail_Service SHALL provide an IMAP server that listens on a configurable host port (default 1143).
2. WHEN a Mail_Client connects to the IMAP_Server with valid credentials, THE IMAP_Server SHALL authenticate the user and present the user's Maildir as a selectable mailbox within 10 seconds.
3. WHEN a Mail_Client requests a folder listing, THE IMAP_Server SHALL return at minimum the standard INBOX folder containing delivered messages.
4. THE IMAP_Server SHALL support the IMAP4rev1 protocol (RFC 3501) for compatibility with standard mail clients.
5. IF a Mail_Client connects with invalid credentials, THEN THE IMAP_Server SHALL reject the connection with an IMAP NO authentication failure response and not expose mailbox contents.
6. WHEN a Mail_Client selects the INBOX and requests a message, THE IMAP_Server SHALL return the full message content including headers and body.
7. WHEN the Mail_Service starts, THE IMAP_Server SHALL begin accepting client connections within 30 seconds.

### Requirement 3: Mail User Configuration

**User Story:** As a stack operator, I want to configure mail users through environment variables, so that team members can authenticate to the IMAP server without manual container configuration.

#### Acceptance Criteria

1. THE Mail_Service SHALL read user accounts from a TJ_MAIL_USERS environment variable formatted as a comma-separated list of user:password pairs (e.g., "alice:secret1,bob:secret2"), supporting between 1 and 50 user entries where each username is 1 to 64 characters and each password is 1 to 128 characters.
2. WHEN the Mail_Service starts with a TJ_MAIL_USERS value where every entry matches the pattern username:password separated by commas, THE Mail_Service SHALL create local system accounts and Maildir directories for each defined user.
3. IF TJ_MAIL_USERS is empty or unset, THEN THE Mail_Service SHALL create a single default account using the local-part of TJ_MAIL_SENDER (the portion before the @ character) as the username with a password equal to that same local-part.
4. IF TJ_MAIL_USERS contains an entry that does not match the user:password format, THEN THE Mail_Service SHALL log an error message indicating the malformed entry and SHALL skip that entry while processing remaining valid entries.
5. WHEN a new message is delivered to a configured user, THE SMTP_Server SHALL store the message in that user's Maildir.

### Requirement 4: Removal of External SMTP Relay Dependency

**User Story:** As a stack operator, I want the stack to operate without external SMTP credentials, so that setup is simpler and the system works in air-gapped environments.

#### Acceptance Criteria

1. THE Mail_Service SHALL send outbound notification and reminder emails via the local SMTP_Server without requiring TJ_SMTP_HOST, TJ_SMTP_PORT, TJ_SMTP_USER, or TJ_SMTP_PASSWORD environment variables.
2. WHEN the Mail_Service starts without TJ_SMTP_HOST, TJ_SMTP_PORT, TJ_SMTP_USER, and TJ_SMTP_PASSWORD environment variables, THE Mail_Service SHALL start and accept SMTP connections within 30 seconds, delivering messages to local Maildir storage.
3. THE Mail_Service SHALL accept optional TJ_SMTP_RELAY_HOST and TJ_SMTP_RELAY_PORT (default 25) environment variables for environments that require forwarding mail to an external destination.
4. IF TJ_SMTP_RELAY_HOST is set, THEN THE SMTP_Server SHALL relay messages addressed to non-local domains through the specified relay host and port instead of rejecting them.
5. IF TJ_SMTP_RELAY_HOST is set and the relay host is unreachable, THEN THE SMTP_Server SHALL queue the message for retry and log an error message indicating the relay connection failure.

### Requirement 5: Cross-Linked Reports

**User Story:** As a project manager, I want each generated report to contain navigation links to all other reports, so that I can move between Gantt charts, resource views, task lists, and cost reports without returning to a directory listing.

#### Acceptance Criteria

1. WHEN the Report_Generator compiles reports, THE Report_Generator SHALL include a navigation header in each HTML report containing links to all other reports in the set and to the Report_Index.
2. THE Cross_Link elements SHALL use relative file paths so reports remain navigable when served from any directory or opened locally.
3. WHEN a report is viewed in a browser, THE navigation header SHALL apply a visually distinct style (such as a different CSS class) to the currently active report's link, differentiating it from the other navigation links.
4. THE Report_Generator SHALL generate a Report_Index page listing all reports with their headline titles as defined in the project configuration and links to each report file.
5. WHEN a new report type is added to the project configuration, THE Report_Generator SHALL automatically include the new report in all navigation headers and the Report_Index on the next compilation.
6. THE navigation header SHALL include a link to the admin panel using a relative path so the link resolves correctly regardless of the host port configuration.
7. IF a report fails to compile, THEN THE Report_Generator SHALL still include that report's link in the navigation headers of successfully compiled reports, and the link SHALL point to the expected filename.

### Requirement 6: Journal Report

**User Story:** As a project manager, I want a journal report showing status entries and notes recorded against tasks, so that I can review project progress and team updates in one place.

#### Acceptance Criteria

1. THE Report_Generator SHALL produce a Journal_Report containing all journal entries defined in the project file, displaying each entry with its associated task name.
2. WHEN a journal entry includes a date, author, and summary, THE Journal_Report SHALL display all three fields for each entry.
3. IF a journal entry is missing the author or summary field, THEN THE Journal_Report SHALL still display the entry with available fields and leave missing fields blank.
4. THE Journal_Report SHALL sort entries in reverse chronological order (newest first), with entries sharing the same date ordered alphabetically by task name.
5. THE Journal_Report SHALL include the Cross_Link navigation header consistent with all other reports.
6. WHEN no journal entries exist in the project, THE Journal_Report SHALL display an informational message indicating no entries are available.

### Requirement 7: IMAP Port Exposure

**User Story:** As a stack operator, I want the IMAP port to be exposed on the Docker host, so that mail clients on the host network can connect to read mail.

#### Acceptance Criteria

1. THE Docker Compose configuration SHALL map the IMAP_Server container port 143 to a configurable host port defined by TJ_IMAP_PORT (default 1143), accepting values in the range 1-65535.
2. WHEN a Mail_Client connects to the host on TJ_IMAP_PORT, THE connection SHALL be forwarded to port 143 on the IMAP_Server inside the Mail_Service container.
3. THE Docker Compose configuration SHALL bind the IMAP port mapping to 127.0.0.1 by default, restricting access to the local host.
4. IF the Docker Compose stack fails to start because TJ_IMAP_PORT is already in use on the host, THEN Docker SHALL report a port conflict error and the Mail_Service container SHALL not start.

### Requirement 8: Mail Data Persistence

**User Story:** As a stack operator, I want mail data to persist across container restarts, so that messages are not lost when the stack is restarted.

#### Acceptance Criteria

1. THE Docker Compose configuration SHALL define a named volume for Maildir storage, mounted at the directory where user Maildir folders are stored inside the Mail_Service container.
2. WHEN the Mail_Service container is stopped and started, or removed and recreated via `docker compose down` followed by `docker compose up`, THE IMAP_Server SHALL serve all previously delivered messages from the persisted Maildir volume.
3. THE Maildir volume SHALL be separate from the existing mail-spool volume used for Postfix queue data.
4. IF the Mail_Service container is recreated while the named Maildir volume exists, THEN THE Mail_Service SHALL reuse the existing volume without requiring manual intervention or data migration.
