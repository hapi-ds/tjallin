# Requirements Document

## Introduction

This feature integrates a locally-hosted LLM agent chat into the tjallin system, delivered through a unified NiceGUI web application that replaces the existing Ruby-based tj-web service. The new `tj-web` service consolidates the report viewer, admin panel, and agent chat into a single Python application. The agent connects to LM Studio running on the user's machine and provides a conversational interface for managing the TaskJuggler project. Users can ask the agent to review the current project plan, update tasks and resources, write booking/timesheet entries, and create journal entries — all through natural language interaction in the browser. The agent reads and writes TaskJuggler `.tjp` and `.tji` files directly, ensuring changes are syntactically valid before persisting them.

## Glossary

- **Agent**: The LLM-powered conversational assistant that interprets user requests and performs actions on the TaskJuggler project files
- **LM_Studio_Backend**: The locally-running LM Studio server that provides the LLM inference API (OpenAI-compatible endpoint)
- **Chat_Service**: The Python service (built with NiceGUI) that manages conversation state, routes user messages to the Agent, executes tool calls against the project files, and serves the web interface
- **Project_Plan**: The collection of TaskJuggler files (`.tjp` and `.tji`) that define the project schedule, resources, tasks, and reports
- **Booking**: A TaskJuggler timesheet entry recording hours worked by a resource on a specific task during a time period
- **Journal_Entry**: A TaskJuggler `journalentry` statement attached to a task, recording status updates, notes, or decisions with a date and author
- **Tool_Call**: A structured action the Agent requests the Chat_Service to execute (e.g., read file, write file, list tasks)
- **Conversation**: A sequence of user messages and Agent responses within a single chat session
- **NiceGUI_App**: The unified web application built with NiceGUI that hosts the report viewer, admin panel, and chat interface on separate pages
- **TJ_Reference_Docs**: The locally bundled TaskJuggler reference documentation (sourced from taskjuggler.org or the tj3 gem) that provides comprehensive syntax definitions for all TJ constructs, stored within the Docker image for offline availability

## Requirements

### Requirement 1: LM Studio Connection

**User Story:** As a project manager, I want the agent to connect to my local LM Studio instance, so that all inference runs on my machine without sending data to external services.

#### Acceptance Criteria

1. WHEN the Chat_Service starts, THE Chat_Service SHALL verify connectivity to the LM_Studio_Backend by sending a request to the models endpoint at the configured URL and confirming a valid response is received within 10 seconds
2. IF the LM_Studio_Backend does not respond within 10 seconds or the connection is refused, THEN THE Chat_Service SHALL return an error message indicating the connection failure and the configured endpoint URL
3. THE Chat_Service SHALL use the OpenAI-compatible chat completions API provided by LM_Studio_Backend
4. WHERE a custom model name is configured, THE Chat_Service SHALL use that model name in API requests to LM_Studio_Backend
5. IF no custom model name is configured, THEN THE Chat_Service SHALL request the list of available models from LM_Studio_Backend and use the first model returned
6. IF no endpoint URL is configured, THEN THE Chat_Service SHALL default to `http://localhost:1234/v1`

### Requirement 2: Project Plan Review

**User Story:** As a project manager, I want to ask the agent about the current state of my project, so that I can quickly understand schedules, resource allocations, and task status without reading raw TaskJuggler files.

#### Acceptance Criteria

1. WHEN the user asks about the project plan, THE Agent SHALL read the `.tjp` file and all `.tji` files in the project directory and its subdirectories that are referenced by the query topic (tasks, resources, accounts, or reports)
2. WHEN the user asks about tasks, THE Agent SHALL present task names, effort, allocations, dependencies, and completion status organized by task hierarchy (parent tasks and subtasks) using labeled fields
3. WHEN the user asks about resources, THE Agent SHALL present resource names, working hours, rates, and vacation periods
4. WHEN the user asks about the project timeline, THE Agent SHALL present the project start date, project end date, and all milestone names with their dependency-derived dates
5. THE Agent SHALL have read access to all `.tjp` and `.tji` files in the project directory and its subdirectories
6. IF a referenced `.tjp` or `.tji` file is missing or unreadable, THEN THE Agent SHALL inform the user which file could not be read and present the information available from the remaining accessible files

### Requirement 3: Project Plan Updates

**User Story:** As a project manager, I want to tell the agent to update tasks, resources, or dependencies in the project plan, so that I can make changes through natural language without editing TaskJuggler syntax manually.

#### Acceptance Criteria

1. WHEN the user requests a task modification, THE Agent SHALL identify the target task in the tasks include file by matching the user's description to existing task IDs or task names, and update that task's attributes with valid TaskJuggler syntax
2. WHEN the user requests a new task, THE Agent SHALL add the task definition to the tasks include file within the correct hierarchical position, including at minimum a task ID, name, effort, and allocation with valid TaskJuggler syntax
3. WHEN the user requests a resource modification, THE Agent SHALL update the resources include file with valid TaskJuggler syntax
4. WHEN the Chat_Service is about to write changes to a project file, THE Chat_Service SHALL invoke the TaskJuggler compiler (tj3) against the full project to validate that the modified content produces no compilation errors
5. IF validation of modified content fails, THEN THE Agent SHALL present the tj3 compiler error output to the user, not persist the invalid changes, and retain the original file unchanged
6. WHEN the Agent modifies a project file, THE Chat_Service SHALL create a backup copy of the original file with a `.bak` extension in the same directory before writing changes
7. IF the user's modification request references a task or resource that cannot be uniquely matched to an existing entry in the Project_Plan, THEN THE Agent SHALL present the ambiguous matches to the user and request clarification before proceeding
8. WHEN the user requests a dependency modification, THE Agent SHALL verify that the referenced dependent and predecessor task paths exist in the Project_Plan before writing the change

### Requirement 4: Booking (Timesheet) Writing

**User Story:** As a team member, I want to tell the agent to record my hours on tasks, so that I can submit timesheets through conversation instead of writing TaskJuggler timesheet syntax.

#### Acceptance Criteria

1. WHEN the user requests to log time, THE Agent SHALL generate a valid TaskJuggler `timesheet` block with the specified resource, date range, task path, and hours, where hours is a positive value not exceeding the resource's defined weekly working hours per task entry and total hours across all task entries not exceeding the resource's weekly working capacity
2. THE Agent SHALL write booking files to the project timesheets directory using the naming convention `YYYY-Www-<resource_id>.tji`
3. IF a timesheet file already exists for the specified week and resource, THEN THE Agent SHALL merge the new task entry into the existing timesheet block, replacing any entry for the same task path and preserving entries for other tasks
4. WHEN the user specifies a status for a booking, THE Agent SHALL include a valid `status` line with color (green, yellow, or red) and headline text
5. IF the user references a task path that does not exist in the Project_Plan, THEN THE Agent SHALL inform the user that the task was not found and list up to 5 task paths with the highest lexical similarity
6. IF the user references a resource ID that does not exist in the Project_Plan, THEN THE Agent SHALL inform the user that the resource was not found and list the available resource IDs
7. IF the user does not specify a date range, THEN THE Agent SHALL default to the current ISO week
8. WHEN the user requests to log time on multiple tasks in a single request, THE Agent SHALL include all specified task entries within a single `timesheet` block for that resource and week

### Requirement 5: Journal Entry Writing

**User Story:** As a project manager, I want to dictate journal entries to the agent, so that I can record project decisions, status updates, and notes without editing files manually.

#### Acceptance Criteria

1. WHEN the user requests a journal entry and specifies a task, THE Agent SHALL generate a valid TaskJuggler `journalentry` statement with the specified date, author, a headline of at most 120 characters, and optional summary, and append it to that task's include file
2. WHEN the user requests a journal entry without specifying a task, THE Agent SHALL append the journal entry to a dedicated journal include file in the project includes directory
3. IF the user does not specify a date for the journal entry, THEN THE Agent SHALL use the current date in YYYY-MM-DD format
4. IF the user does not specify an author for the journal entry, THEN THE Agent SHALL use a configured default author resource ID
5. IF the configured default author resource ID is not set and the user does not specify an author, THEN THE Agent SHALL prompt the user to provide an author resource ID before generating the entry
6. IF the user references a task that does not exist in the Project_Plan, THEN THE Agent SHALL inform the user that the task was not found and list similar task paths
7. IF the user specifies an author resource ID that does not exist in the Project_Plan, THEN THE Agent SHALL inform the user that the resource was not found and list available resource IDs

### Requirement 6: Conversation Management

**User Story:** As a user, I want the chat to maintain context within a session, so that I can have multi-turn conversations where the agent remembers what we discussed earlier.

#### Acceptance Criteria

1. THE Chat_Service SHALL maintain conversation history as an ordered list of messages (including user messages, Agent responses, and Tool_Call results) for the duration of a chat session
2. WHEN the user sends a message, THE Chat_Service SHALL include all conversation history from the current session in the prompt sent to LM_Studio_Backend, up to the configured token limit
3. IF the conversation history exceeds the configured token limit, THEN THE Chat_Service SHALL truncate messages starting from the oldest while preserving the system prompt and at minimum the 4 most recent exchanges (where one exchange is a user message and its corresponding Agent response)
4. WHEN a new chat session starts, THE Chat_Service SHALL initialize with a system prompt that lists the project directory file names, describes the purpose of each include file, and enumerates the available Tool_Calls by name
5. WHEN the Agent executes a Tool_Call, THE Chat_Service SHALL include the Tool_Call request and its result in the conversation history so that subsequent messages retain context of actions performed

### Requirement 7: Tool Execution Safety

**User Story:** As a user, I want the agent to confirm destructive changes before applying them, so that I do not accidentally corrupt my project files.

#### Acceptance Criteria

1. WHEN the Agent proposes a write operation (file creation, modification, or deletion), THE Agent SHALL present a summary to the user that includes the target file path, the type of operation, and a description of the content to be changed, and SHALL request explicit confirmation before proceeding
2. IF the user declines a proposed change, THEN THE Agent SHALL discard the change, preserve the original file state, and acknowledge the cancellation to the user
3. THE Chat_Service SHALL restrict file operations to the project directory and its subdirectories only
4. IF a Tool_Call attempts to access a path outside the project directory, THEN THE Chat_Service SHALL reject the operation and inform the user that the path is outside the allowed project boundary
5. THE Chat_Service SHALL resolve all file paths to their canonical absolute form (resolving symlinks, `..`, and `.` segments) before evaluating whether the path is within the project directory

### Requirement 8: Proactive Guidance

**User Story:** As a project manager, I want the agent to suggest what to do next based on the current project state, so that I can stay on top of deadlines, overdue tasks, and upcoming milestones without having to ask.

#### Acceptance Criteria

1. WHEN the user asks what to do next, THE Agent SHALL analyze the Project_Plan and suggest up to 5 prioritized next steps based on task status, deadlines within the next 14 calendar days, and resource availability
2. WHEN the user starts a new chat session, THE Agent SHALL proactively summarize the current project status including overdue tasks, milestones due within the next 14 calendar days, and timesheets not yet submitted for the current or previous ISO week by any resource with allocated tasks
3. WHEN the user completes a booking or project update, THE Agent SHALL suggest up to 3 related follow-up actions such as updating dependent tasks, notifying team members, or recording a journal entry
4. IF tasks are past their planned end date without completion, THEN THE Agent SHALL highlight those tasks as overdue, indicate the number of days overdue, and suggest corrective actions such as reassigning resources, adjusting dependencies, or updating the planned end date
5. WHEN the Agent provides proactive suggestions, THE Agent SHALL base all deadline and overdue calculations on the `now` date configured in the Project_Plan

### Requirement 9: Report and Presentation Expertise

**User Story:** As a project manager, I want the agent to help me create professional Gantt charts and reports, so that I can produce high-quality project presentations without mastering TaskJuggler report syntax.

#### Acceptance Criteria

1. WHEN the user requests a new report, THE Agent SHALL generate a valid TaskJuggler report definition with columns, sorting, filtering, and formatting that match the selected report type's standard attributes
2. WHEN the user asks for a Gantt chart configuration, THE Agent SHALL produce a `taskreport` definition with timeline, dependencies, milestones, and critical path visualization
3. WHEN the user asks which report type to use, THE Agent SHALL recommend from the supported TaskJuggler report types (`taskreport`, `resourcereport`, `accountreport`, `textreport`, `statusreport`) based on the data the user wants to present
4. WHEN the user asks to customize report appearance, THE Agent SHALL apply TaskJuggler formatting options such as column selection, sort order, hide expressions, roll-up settings, and time scales
5. WHEN the user requests a report for a specific audience, THE Agent SHALL adjust the report by varying column count, hide expressions, and roll-up level so that executive-level reports show summary milestones and costs only, while team-level reports show individual task assignments, effort, and dependencies
6. THE Agent SHALL write report definitions to the reports include file using valid TaskJuggler syntax
7. IF a report definition with the same identifier already exists in the reports include file, THEN THE Agent SHALL inform the user of the conflict and offer to replace the existing report or use a different identifier

### Requirement 10: Documentation Updates

**User Story:** As a maintainer, I want the project documentation to reflect the new agent chat capability, so that users know how to configure and use the feature.

#### Acceptance Criteria

1. WHEN the feature is complete, THE README.md SHALL include a section describing the LLM agent chat capability, its purpose, and the URL to access the chat interface
2. WHEN the feature is complete, THE docs/user-guide.md SHALL include instructions for installing and configuring LM Studio, accessing the web interface, and using each supported command (/reset, /help)
3. THE docs/user-guide.md SHALL document all environment variables related to the LLM agent chat in the Configuration Reference table, including for each variable: name, required or optional status, default value, and description
4. THE docs/user-guide.md SHALL include at least one example conversation for each of the following capabilities: plan review, task/resource updates, booking creation, journal entry creation, and report creation
5. WHEN the feature is complete, THE README.md SHALL list the LM Studio prerequisite with minimum compatible version in the Quick Start section or a linked setup section

### Requirement 11: Web-Based Chat Interface

**User Story:** As a user, I want to interact with the agent through a browser-based chat interface, so that I can send messages and receive responses in a modern, accessible UI.

#### Acceptance Criteria

1. THE NiceGUI_App SHALL expose a chat page at the `/chat` URL path that displays a message input field and a scrollable message history area
2. WHEN the user sends a message via the chat input, THE Chat_Service SHALL display the complete Agent response within the chat message area within 120 seconds or display a timeout error inline
3. WHEN the Agent is processing a request, THE chat interface SHALL display a visible loading indicator (spinner or typing animation) until the response is complete
4. WHEN the Agent executes a Tool_Call, THE chat interface SHALL display the tool name and a single-line summary of the action taken as a system message in the conversation
5. THE chat interface SHALL support a `/reset` command (typed in the message input) to clear conversation history and start a new session
6. THE chat interface SHALL support a `/help` command that displays all available commands and a summary of agent capabilities as a system message
7. IF the user enters an unrecognized slash command (a message starting with `/` that does not match a supported command), THEN THE chat interface SHALL display an error message indicating the command is unknown and suggest using `/help`
8. IF the user submits empty or whitespace-only input, THEN THE chat interface SHALL ignore the input without sending a request to the Agent
9. WHEN the Agent proposes a write operation requiring confirmation, THE chat interface SHALL display the proposal with Accept and Decline buttons inline in the conversation
10. THE chat interface SHALL visually distinguish between user messages, Agent responses, system messages, and tool action summaries using different styling or alignment

### Requirement 12: Unified Web Application (NiceGUI)

**User Story:** As a project manager, I want a single web application that combines report viewing, project administration, and agent chat, so that I can manage all aspects of my project from one browser tab.

#### Acceptance Criteria

1. THE NiceGUI_App SHALL serve as the replacement for the existing Ruby-based tj-web service, running as a Python application within the tj-web Docker container
2. THE NiceGUI_App SHALL provide a navigation layout with links to Reports, Admin, and Chat pages accessible from every page
3. THE NiceGUI_App SHALL serve the TaskJuggler-generated HTML reports at the `/reports` URL path by embedding or linking to the report files from the reports volume
4. THE NiceGUI_App SHALL provide an admin page at the `/admin` URL path with buttons to trigger project compilation (rebuild reports), view timesheet status, and view system status
5. WHEN the user clicks the rebuild button on the admin page, THE NiceGUI_App SHALL invoke the tj3 compiler against the project and display the result (success with report count, or failure with error details)
6. THE NiceGUI_App SHALL listen on port 8080 for all web traffic (reports, admin, and chat)
7. THE NiceGUI_App SHALL display a project status summary on the home page (`/`) showing report count, timesheet count, project file status, and a link to the chat
8. IF the LM_Studio_Backend is not reachable, THEN THE chat page SHALL display a connection error banner with the configured endpoint URL and a retry button, while the reports and admin pages remain fully functional

### Requirement 13: TaskJuggler Documentation Integration

**User Story:** As a project manager, I want the agent to have comprehensive knowledge of TaskJuggler syntax from the official reference manual, so that it can generate correct and complete TJ constructs beyond what the LLM remembers from training data.

#### Acceptance Criteria

1. THE Chat_Service SHALL include a local copy of the TaskJuggler reference documentation stored within the project repository or Docker image at a configured path
2. WHEN the Docker image is built, THE build process SHALL bundle the TaskJuggler reference documentation so that it is available offline without network access
3. WHEN a new chat session starts, THE Chat_Service SHALL include key TaskJuggler syntax sections (task, resource, account, report, timesheet, journalentry, and macro definitions) from the bundled documentation in the system prompt provided to LM_Studio_Backend
4. IF the bundled documentation exceeds the available token budget for the system prompt, THEN THE Chat_Service SHALL include a condensed syntax reference covering the most commonly used constructs and provide the full documentation as a searchable tool
5. THE Chat_Service SHALL expose a `search_tj_docs` Tool_Call that accepts a query string and returns relevant sections from the bundled TaskJuggler documentation matching the query
6. WHEN the Agent generates TaskJuggler syntax for any construct, THE Agent SHALL reference the bundled documentation to ensure the output uses valid attribute names, correct nesting rules, and supported value formats as defined in the TaskJuggler reference
7. THE bundled documentation SHALL cover at minimum the following TaskJuggler constructs: project, task, resource, account, shift, vacation, timesheet, statussheet, journalentry, report types (taskreport, resourcereport, accountreport, textreport, statusreport), macros, includes, and all standard column identifiers
8. IF the bundled documentation file is missing or unreadable at startup, THEN THE Chat_Service SHALL log a warning and continue operation using the LLM's built-in knowledge, and SHALL display a notice on the chat page indicating that enhanced TJ syntax support is unavailable
