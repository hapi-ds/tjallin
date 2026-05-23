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
5. IF a message is addressed to an unknown domain, THEN THE SMTP_Server SHALL reject the message with an appropriate error code.

### Requirement 2: IMAP Access for Mail Clients

**User Story:** As a project team member, I want to connect a standard mail client to the stack via IMAP, so that I can read timesheet reminders and system notifications in my preferred email application.

#### Acceptance Criteria

1. THE Mail_Service SHALL provide an IMAP server that listens on a configurable host port (default 1143).
2. WHEN a Mail_Client connects to the IMAP_Server with valid credentials, THE IMAP_Server SHALL grant access to the user's Maildir.
3. WHEN a Mail_Client requests a folder listing, THE IMAP_Server SHALL return the standard INBOX folder containing delivered messages.
4. THE IMAP_Server SHALL support the IMAP4rev1 protocol for compatibility with standard mail clients.
5. WHEN a Mail_Client connects with invalid credentials, THE IMAP_Server SHALL reject the connection with an authentication failure response.

### Requirement 3: Mail User Configuration

**User Story:** As a stack operator, I want to configure mail users through environment variables, so that team members can authenticate to the IMAP server without manual container configuration.

#### Acceptance Criteria

1. THE Mail_Service SHALL read user accounts from a TJ_MAIL_USERS environment variable formatted as a comma-separated list of user:password pairs.
2. WHEN the Mail_Service starts with a valid TJ_MAIL_USERS value, THE Mail_Service SHALL create local system accounts and Maildir directories for each defined user.
3. IF TJ_MAIL_USERS is empty or unset, THEN THE Mail_Service SHALL create a single default account using the value of TJ_MAIL_SENDER as the username.
4. WHEN a new message is delivered to a configured user, THE SMTP_Server SHALL store the message in that user's Maildir.

### Requirement 4: Removal of External SMTP Relay Dependency

**User Story:** As a stack operator, I want the stack to operate without external SMTP credentials, so that setup is simpler and the system works in air-gapped environments.

#### Acceptance Criteria

1. THE Mail_Service SHALL send outbound notification and reminder emails via the local SMTP_Server without requiring TJ_SMTP_HOST, TJ_SMTP_PORT, TJ_SMTP_USER, or TJ_SMTP_PASSWORD environment variables.
2. WHEN the Mail_Service starts without external SMTP relay variables, THE Mail_Service SHALL start successfully and deliver mail locally.
3. THE Mail_Service SHALL retain the ability to accept an optional TJ_SMTP_RELAY_HOST variable for environments that require forwarding mail to an external destination.
4. IF TJ_SMTP_RELAY_HOST is set, THEN THE SMTP_Server SHALL relay outbound messages through the specified host instead of delivering locally.

### Requirement 5: Cross-Linked Reports

**User Story:** As a project manager, I want each generated report to contain navigation links to all other reports, so that I can move between Gantt charts, resource views, task lists, and cost reports without returning to a directory listing.

#### Acceptance Criteria

1. WHEN the Report_Generator compiles reports, THE Report_Generator SHALL include a navigation header in each HTML report containing links to all other reports in the set.
2. THE Cross_Link elements SHALL use relative file paths so reports remain navigable when served from any directory or opened locally.
3. WHEN a report is viewed in a browser, THE navigation header SHALL visually indicate which report is currently active.
4. THE Report_Generator SHALL generate a Report_Index page listing all reports with descriptive titles and links.
5. WHEN a new report type is added to the project configuration, THE Report_Generator SHALL automatically include the new report in all navigation headers and the Report_Index.

### Requirement 6: Journal Report

**User Story:** As a project manager, I want a journal report showing status entries and notes recorded against tasks, so that I can review project progress and team updates in one place.

#### Acceptance Criteria

1. THE Report_Generator SHALL produce a Journal_Report containing all journal entries defined in the project file.
2. WHEN a journal entry includes a date, author, and summary, THE Journal_Report SHALL display all three fields for each entry.
3. THE Journal_Report SHALL sort entries in reverse chronological order (newest first).
4. THE Journal_Report SHALL include the Cross_Link navigation header consistent with all other reports.
5. WHEN no journal entries exist in the project, THE Journal_Report SHALL display an informational message indicating no entries are available.

### Requirement 7: IMAP Port Exposure

**User Story:** As a stack operator, I want the IMAP port to be exposed on the Docker host, so that mail clients on the host network can connect to read mail.

#### Acceptance Criteria

1. THE Docker Compose configuration SHALL map the IMAP_Server port to a configurable host port defined by TJ_IMAP_PORT (default 1143).
2. WHEN a Mail_Client connects to the host on TJ_IMAP_PORT, THE connection SHALL be forwarded to the IMAP_Server inside the Mail_Service container.
3. THE Docker Compose configuration SHALL expose the IMAP port only on localhost (127.0.0.1) by default for security.

### Requirement 8: Mail Data Persistence

**User Story:** As a stack operator, I want mail data to persist across container restarts, so that messages are not lost when the stack is restarted.

#### Acceptance Criteria

1. THE Docker Compose configuration SHALL define a named volume for Maildir storage.
2. WHEN the Mail_Service container restarts, THE IMAP_Server SHALL serve previously delivered messages from the persisted Maildir volume.
3. THE Maildir volume SHALL be separate from the existing mail-spool volume used for Postfix queue data.
