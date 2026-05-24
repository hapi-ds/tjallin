# Requirements Document

## Introduction

A built-in manual editor for TaskJuggler project files (.tjp and .tji) within the existing NiceGUI web application. The editor provides a file tree browser, a code editor with TJ syntax highlighting, compiler-validated save functionality, and an inline agentic helper panel for context-aware TJ syntax assistance. The editor is accessible at `/editor` and integrates with the existing navigation, services, and infrastructure.

## Glossary

- **Editor_Page**: The NiceGUI page served at `/editor` containing the file tree, code editor, and helper panel.
- **File_Tree**: A sidebar component displaying the hierarchical structure of project files (.tjp and .tji) within the configured project directory.
- **Code_Editor**: A browser-based code editing component (CodeMirror or equivalent) with syntax highlighting for TaskJuggler files.
- **Helper_Panel**: An inline chat/suggestion panel adjacent to the Code_Editor where users interact with the LLM for TJ syntax assistance.
- **Path_Safety_Module**: The existing `path_safety.py` module that restricts file access to the project directory boundary.
- **Compiler_Validator**: The existing tj3 compiler integration that validates project files before persisting changes.
- **ChatService**: The existing service that manages LLM communication via the OpenAI-compatible API to LM Studio.
- **TJDocumentationService**: The existing service providing searchable TaskJuggler reference documentation.
- **Project_Directory**: The configurable directory (settings.project_path) where TaskJuggler project files are stored.
- **Diff_Suggestion**: A proposed code change from the Helper_Panel presented as a before/after diff that the user can accept or reject.

## Requirements

### Requirement 1: Editor Page Routing and Navigation

**User Story:** As a user, I want to access the project file editor from the main navigation, so that I can edit project files without leaving the web application.

#### Acceptance Criteria

1. THE Editor_Page SHALL be accessible at the URL path `/editor`.
2. THE Editor_Page SHALL appear as a navigation link labeled "Editor" in the shared navigation header alongside Home, Reports, Admin, and Chat, with the "Editor" link visually indicated as active when the current path is `/editor`.
3. WHEN a user navigates to `/editor`, THE Editor_Page SHALL render the File_Tree, Code_Editor, and Helper_Panel arranged side by side at viewport widths of 1024px and above, and stacked vertically at viewport widths below 1024px.

### Requirement 2: File Tree Browser

**User Story:** As a user, I want to browse all project files in a tree structure, so that I can quickly find and select files to edit.

#### Acceptance Criteria

1. THE File_Tree SHALL display all files and directories within the Project_Directory as a hierarchical tree structure, sorted alphabetically with directories listed before files.
2. THE File_Tree SHALL display files with extensions `.tjp` and `.tji` with distinct visual indicators that differentiate `.tjp` files, `.tji` files, and other file types from each other.
3. WHEN a user clicks a file in the File_Tree and the Code_Editor contains no unsaved changes, THE Code_Editor SHALL load the content of the selected file.
4. WHEN the Project_Directory contains subdirectories, THE File_Tree SHALL display them as collapsible nodes that are collapsed by default.
5. THE File_Tree SHALL exclude hidden files and directories (names starting with a dot).
6. THE File_Tree SHALL use the Path_Safety_Module to validate that all displayed paths are within the Project_Directory boundary.
7. WHEN a user clicks a file in the File_Tree and the Code_Editor contains unsaved changes, THE Editor_Page SHALL prompt the user to confirm discarding unsaved changes before loading the new file.
8. IF a file cannot be read when selected in the File_Tree, THEN THE Editor_Page SHALL display an error message indicating the file could not be loaded and SHALL retain the previously loaded file content in the Code_Editor.

### Requirement 3: Code Editor with Syntax Highlighting

**User Story:** As a user, I want a code editor with TaskJuggler syntax highlighting, so that I can read and edit project files with visual clarity.

#### Acceptance Criteria

1. THE Code_Editor SHALL render file content in a code editing component with monospace font and line numbers.
2. THE Code_Editor SHALL apply syntax highlighting for TaskJuggler keywords (task, resource, project, account, shift, booking, supplement, and all other reserved TJ identifiers), single-line comments (# and //), block comments (/* */), quoted strings, and numeric values including date literals.
3. THE Code_Editor SHALL support standard text editing operations including undo (at least 50 operations deep), redo, find, and replace.
4. WHEN a file is loaded into the Code_Editor, THE Code_Editor SHALL display the file path in the header or tab indicator, truncating paths longer than 60 characters with a leading ellipsis to show the file name portion.
5. WHEN the user modifies content in the Code_Editor, THE Code_Editor SHALL indicate unsaved changes by displaying an asterisk (*) adjacent to the file name in the header or tab indicator.
6. WHEN a save operation completes successfully, THE Code_Editor SHALL remove the unsaved changes indicator from the header or tab indicator.
7. THE Code_Editor SHALL preserve the cursor position and scroll state when the file content is refreshed after a save operation.
8. IF a file fails to load due to a read error, THEN THE Code_Editor SHALL display an error message indicating the file could not be read and retain the previous editor state.
9. WHEN no file is selected, THE Code_Editor SHALL display a placeholder message instructing the user to select a file from the File_Tree.

### Requirement 4: Save with Compiler Validation

**User Story:** As a user, I want my changes validated by the tj3 compiler before they are saved, so that I cannot accidentally introduce syntax errors into the project.

#### Acceptance Criteria

1. WHEN the user triggers a save action via the save button or a Ctrl+S keyboard shortcut, THE Editor_Page SHALL write the editor content to a temporary file within the Project_Directory and invoke the Compiler_Validator.
2. WHEN the Compiler_Validator reports success, THE Editor_Page SHALL persist the content to the target file and remove the temporary file.
3. WHEN the Compiler_Validator reports failure, THE Editor_Page SHALL display the compiler error messages from stderr to the user and retain the original file content unchanged on disk.
4. WHEN the Compiler_Validator reports failure, THE Code_Editor SHALL retain the user's edited content so the user can fix the errors without losing work.
5. WHEN a save operation is initiated and the target file already exists, THE Editor_Page SHALL create a backup of the original file before persisting validated changes.
6. THE Editor_Page SHALL use the Path_Safety_Module to validate the target file path before any write operation.
7. WHEN a save operation is in progress, THE Editor_Page SHALL disable the save button and display a loading indicator until the operation completes or times out.
8. IF the Compiler_Validator does not respond within 30 seconds, THEN THE Editor_Page SHALL abort the save operation, display a timeout error message to the user, and retain the original file content unchanged.
9. IF the Compiler_Validator is unavailable (tj3 binary not found), THEN THE Editor_Page SHALL abort the save operation and display an error message indicating the compiler is not installed.
10. IF backup creation fails before persisting changes, THEN THE Editor_Page SHALL abort the save operation and display an error message indicating the backup could not be created.

### Requirement 5: Agentic Helper Panel

**User Story:** As a user, I want an inline AI assistant that understands TaskJuggler syntax, so that I can get help writing and fixing TJ code without leaving the editor.

#### Acceptance Criteria

1. THE Helper_Panel SHALL be displayed to the right of the Code_Editor as a collapsible side panel that defaults to the expanded state when the Editor_Page loads.
2. THE Helper_Panel SHALL provide a toggle button that collapses the panel to a minimal-width indicator and expands it back to its full width.
3. THE Helper_Panel SHALL provide a text input with a maximum length of 2000 characters where the user can type questions or requests about TJ syntax.
4. IF the user submits empty or whitespace-only input in the Helper_Panel, THEN THE Helper_Panel SHALL ignore the submission without sending a request to the ChatService.
5. WHEN the user submits a message in the Helper_Panel, THE Helper_Panel SHALL send the message along with the current file content and cursor position to the ChatService.
6. WHEN the user submits a message in the Helper_Panel, THE Helper_Panel SHALL display a loading indicator until the ChatService response is received or a 120-second timeout elapses.
7. IF the ChatService does not respond within 120 seconds, THEN THE Helper_Panel SHALL display an error message indicating the request timed out.
8. THE Helper_Panel SHALL display the LLM response in a scrollable conversation area that retains all messages from the current editor session.
9. THE Helper_Panel SHALL include the TJDocumentationService search results relevant to the user's query in the context sent to the ChatService, so that responses are grounded in the bundled TJ reference documentation.
10. IF the ChatService is unreachable, THEN THE Helper_Panel SHALL display an error message indicating the LLM service is unavailable and provide a retry button.

### Requirement 6: Diff-Based Suggestion Workflow

**User Story:** As a user, I want the AI helper to suggest code changes as diffs that I can accept or reject, so that I maintain control over what gets applied to my files.

#### Acceptance Criteria

1. WHEN the LLM response contains a fenced code block annotated with a file path and line range, THE Helper_Panel SHALL present that block as a Diff_Suggestion showing the original content from the referenced lines and the proposed replacement content side by side.
2. THE Diff_Suggestion SHALL provide an "Accept" button and a "Reject" button, both visible without scrolling within the suggestion component.
3. WHEN the user clicks "Accept" on a Diff_Suggestion, THE Code_Editor SHALL replace the content at the referenced line range with the suggested content.
4. IF the editor content at the referenced line range has changed since the Diff_Suggestion was generated, THEN THE Code_Editor SHALL not apply the change and THE Helper_Panel SHALL display an indication that the suggestion is outdated due to conflicting edits.
5. WHEN the user clicks "Reject" on a Diff_Suggestion, THE Helper_Panel SHALL remove the Accept and Reject buttons from that suggestion and display it in a visually distinct disabled state without modifying the Code_Editor content.
6. WHEN a Diff_Suggestion is accepted, THE Code_Editor SHALL mark the file as having unsaved changes.
7. THE Helper_Panel SHALL display each Diff_Suggestion within a conversation independently, allowing the user to accept or reject each suggestion in any order regardless of its position in the conversation.
8. WHEN a Diff_Suggestion has been accepted, THE Helper_Panel SHALL remove the Accept and Reject buttons from that suggestion and display it in a visually distinct accepted state.

### Requirement 7: Context-Aware Assistance

**User Story:** As a user, I want the AI helper to understand my current editing context, so that its suggestions are relevant to what I am working on.

#### Acceptance Criteria

1. WHEN the user submits a message in the Helper_Panel, THE Helper_Panel SHALL include the current file name in the context sent to the ChatService.
2. WHEN the user submits a message in the Helper_Panel, THE Helper_Panel SHALL include the current cursor line number and surrounding lines (10 lines above and below) in the context sent to the ChatService.
3. WHEN the user submits a message in the Helper_Panel, THE Helper_Panel SHALL include a list of other project files for cross-reference context.
4. THE Helper_Panel SHALL use a dedicated system prompt that instructs the LLM to respond with TJ syntax assistance and produce structured diff suggestions when appropriate.

### Requirement 8: Path Safety Enforcement

**User Story:** As a user, I want the editor to enforce file access boundaries, so that I cannot accidentally read or write files outside the project directory.

#### Acceptance Criteria

1. THE Editor_Page SHALL validate all file read operations through the Path_Safety_Module before accessing file content.
2. THE Editor_Page SHALL validate all file write operations through the Path_Safety_Module before persisting content.
3. IF a file path resolves to a location outside the Project_Directory, THEN THE Editor_Page SHALL reject the operation and display a security error message.
4. THE File_Tree SHALL only enumerate files within the Project_Directory boundary.

### Requirement 9: Integration with Existing Services

**User Story:** As a user, I want the editor to reuse the existing application infrastructure, so that it behaves consistently with the rest of the application.

#### Acceptance Criteria

1. THE Editor_Page SHALL reuse the existing ChatService for LLM communication in the Helper_Panel.
2. THE Editor_Page SHALL reuse the existing TJDocumentationService for documentation search within the Helper_Panel context.
3. THE Editor_Page SHALL read the Project_Directory path from the existing ChatSettings.project_path configuration.
4. THE Editor_Page SHALL reuse the existing backup and rollback mechanism from the ToolExecutor for save operations.
5. THE Editor_Page SHALL use the same shared navigation header component as all other pages in the application.
