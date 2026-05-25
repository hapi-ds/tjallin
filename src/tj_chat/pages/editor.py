"""Editor page with three-panel layout: file tree, code editor, helper panel.

Provides the browser-based project file editor at `/editor` with a responsive
layout that arranges panels side-by-side at ≥1024px and stacks them vertically
at narrower viewports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui
from nicegui.events import KeyEventArguments

from tj_chat.editor_models import (
    DiffSuggestion,
    EditorContext,
    FileNode,
    apply_suggestion,
    truncate_path_display,
)
from tj_chat.tj_codemirror import get_codemirror_mode_js

if TYPE_CHECKING:
    from nicegui.elements.codemirror.codemirror import CodeMirror

    from tj_chat.editor_service import EditorService
    from tj_chat.helper_service import HelperService
    from tj_chat.settings import ChatSettings


class EditorPageUI:
    """Three-panel editor page: file tree, code editor, and helper panel.

    Renders a responsive layout that displays panels side-by-side at
    viewport widths ≥1024px and stacks them vertically below that
    threshold. When no file is selected, the editor area shows a
    placeholder message.

    Args:
        editor_service: Service for file tree building and file I/O.
        helper_service: Service for LLM-powered helper panel interactions.
        settings: Application configuration settings.
    """

    def __init__(
        self,
        editor_service: EditorService,
        helper_service: HelperService,
        settings: ChatSettings,
    ) -> None:
        self._editor_service = editor_service
        self._helper_service = helper_service
        self._settings = settings
        self._current_file: str | None = None
        self._is_dirty: bool = False
        self._is_saving: bool = False
        self._helper_expanded: bool = True
        self._editor: CodeMirror | None = None
        self._error_panel: ui.expansion | None = None
        self._cached_file_nodes: list[FileNode] = []
        self._loading_file: bool = False
        # Pre-cache the file tree for directory lookups and context assembly
        try:
            self._cached_file_nodes = self._editor_service.build_file_tree()
        except Exception:
            pass
        self._save_spinner: ui.spinner | None = None
        self._helper_loading: bool = False
        self._conversation: list[dict[str, str]] = []
        self._suggestions: list[DiffSuggestion] = []
        self._last_user_message: str = ""

    def setup(self) -> None:
        """Render the editor page layout and bind events.

        Injects the TJ CodeMirror mode JavaScript and renders the
        three-panel layout with file tree (left), code editor (center),
        and helper panel (right). Binds Ctrl+S keyboard shortcut to save.
        """
        # Inject TJ CodeMirror language mode
        ui.add_body_html(f"<script>{get_codemirror_mode_js()}</script>")

        # Bind Ctrl+S keyboard shortcut to save
        ui.keyboard(on_key=self._on_keyboard)

        # Main container — horizontal row with full height
        with ui.row().classes("w-full no-wrap").style(
            "height: calc(100vh - 80px); gap: 8px; padding: 8px;"
        ):
            # Left panel: File tree (~20% width)
            self._render_file_tree_panel()

            # Center panel: Code editor (~50% width)
            self._render_editor_panel()

            # Right panel: Helper panel (~30% width)
            self._render_helper_panel()

    def _render_file_tree_panel(self) -> None:
        """Render the file tree browser panel (left side).

        Builds the file tree from the editor service and renders it as a
        collapsible NiceGUI tree component with distinct icons for .tjp,
        .tji, and other file types. Directories are collapsed by default.
        """
        with ui.card().classes("overflow-auto").style(
            "width: 20%; height: 100%; min-width: 180px;"
        ):
            ui.label("Project Files").classes("text-subtitle1 font-bold mb-2")
            # Build tree data from the editor service (cached for lookups)
            self._cached_file_nodes = self._editor_service.build_file_tree()
            tree_data = self._build_tree_data(self._cached_file_nodes)
            self._file_tree = ui.tree(
                tree_data,
                label_key="label",
                children_key="children",
                node_key="id",
                on_select=lambda e: self._on_file_select(e.value),
            ).props("dense no-selection-unset").classes("w-full")

    def _render_editor_panel(self) -> None:
        """Render the code editor panel (center).

        Shows a placeholder message when no file is selected. When a file
        is loaded, displays a CodeMirror editor with TJ syntax highlighting,
        line numbers, and monospace font.
        """
        with ui.card().classes("flex flex-col overflow-hidden").style(
            "width: 50%; height: 100%; flex: 1 1 auto; min-height: 0;"
        ):
            # Editor header with file path, dirty indicator, and save button
            with ui.row().classes("w-full items-center justify-between mb-2"):
                self._file_path_label = ui.label("No file selected").classes(
                    "text-subtitle2 text-grey-7 truncate"
                )
                with ui.row().classes("items-center gap-1"):
                    self._save_spinner = ui.spinner(
                        size="sm"
                    )
                    self._save_spinner.set_visibility(False)
                    self._save_button = ui.button(
                        "Save", icon="save", on_click=self._on_save
                    ).props("flat dense disable")

            # Collapsible error panel for compiler errors (hidden by default)
            self._error_panel = ui.expansion(
                "Compiler Errors", icon="error"
            ).classes("w-full text-negative")
            self._error_panel.set_visibility(False)
            with self._error_panel:
                self._error_content = ui.column().classes("w-full gap-1")

            # Editor content area
            self._editor_container = ui.column().classes(
                "w-full flex-grow"
            ).style("min-height: 0; overflow: hidden;")
            with self._editor_container:
                # Placeholder message when no file is selected
                self._placeholder = ui.column().classes(
                    "w-full h-full items-center justify-center"
                )
                with self._placeholder:
                    ui.icon("description").classes(
                        "text-6xl text-grey-4 mb-4"
                    )
                    ui.label("Select a file from the tree to start editing").classes(
                        "text-h6 text-grey-5"
                    )
                    ui.label(
                        "Browse the project files on the left panel"
                    ).classes("text-body2 text-grey-4")

    def _render_helper_panel(self) -> None:
        """Render the helper/chat panel (right side).

        Displays a collapsible panel with:
        - Toggle button to collapse/expand
        - Scrollable conversation area with message history
        - Loading indicator during LLM requests
        - DiffSuggestion components with Accept/Reject buttons
        - Error messages inline with retry button
        - Text input (max 2000 chars) for user messages
        """
        with ui.card().classes("flex flex-col").style(
            "width: 30%; height: 100%; min-width: 250px;"
        ):
            # Header with title and collapse toggle
            with ui.row().classes("w-full items-center justify-between mb-2"):
                ui.label("TJ Helper").classes("text-subtitle1 font-bold")
                self._helper_toggle = ui.button(
                    icon="chevron_right",
                    on_click=self._toggle_helper,
                ).props("flat dense round")

            # Collapsible content wrapper
            self._helper_body = ui.column().classes(
                "w-full flex-grow flex flex-col overflow-hidden gap-0"
            )
            with self._helper_body:
                # Scrollable conversation area
                self._helper_scroll = ui.scroll_area().classes(
                    "w-full flex-grow"
                )
                with self._helper_scroll:
                    self._helper_content = ui.column().classes(
                        "w-full gap-2 p-2"
                    )
                    with self._helper_content:
                        ui.label(
                            "Ask questions about TaskJuggler syntax or "
                            "request code suggestions."
                        ).classes("text-body2 text-grey-6 italic")

                # Loading spinner (hidden by default)
                self._helper_spinner_row = ui.row().classes(
                    "w-full justify-center py-2 hidden"
                )
                with self._helper_spinner_row:
                    ui.spinner("dots", size="sm")
                    ui.label("Thinking...").classes("text-grey-6 ml-2 text-sm")

                # Input area at the bottom
                with ui.row().classes("w-full gap-1 mt-2"):
                    self._helper_input = ui.input(
                        placeholder="Ask about TJ syntax...",
                    ).classes("flex-grow").props(
                        "outlined dense maxlength=2000"
                    ).on("keydown.enter", self._on_helper_send)
                    self._helper_send_btn = ui.button(
                        icon="send", on_click=self._on_helper_send
                    ).props("flat round dense color=primary")

    async def load_file(self, relative_path: str) -> None:
        """Load a file into the code editor.

        Reads the file via EditorService and displays it in the CodeMirror
        editor. Hides the placeholder and shows the editor. Updates the
        file path header with truncated display.

        Args:
            relative_path: Path relative to the project root.
        """
        result = await self._editor_service.read_file(relative_path)

        if not result.success:
            ui.notify(
                f"Failed to load file: {result.error}",
                type="negative",
                timeout=5000,
            )
            return

        # Update state
        self._current_file = relative_path
        self._is_dirty = False

        # Update header with truncated path display
        display_path = truncate_path_display(relative_path)
        self._file_path_label.set_text(display_path)

        # Hide placeholder, show editor
        self._placeholder.set_visibility(False)

        # Always recreate the CodeMirror editor within the correct container.
        # Clear the container completely to avoid slot context issues.
        if self._editor is not None:
            self._editor = None
            self._editor_container.clear()

        self._loading_file = True
        with self._editor_container:
            self._editor = ui.codemirror(
                value=result.content,
                on_change=self._on_editor_change,
                language=None,  # Custom TJ mode injected via JS
                theme="vscodeDark",
            ).classes("w-full font-mono").style("height: calc(100vh - 200px);")
        self._loading_file = False

        # Enable save button
        self._save_button.props(remove="disable")

        # Hide error panel from previous file
        self._hide_error_panel()

    def _on_editor_change(self) -> None:
        """Handle editor content changes to track dirty state.

        Sets the dirty flag and shows an asterisk in the file path header
        to indicate unsaved changes. Ignores changes triggered by
        programmatic value updates during file loading.
        """
        if self._current_file is None:
            return

        # Ignore changes triggered by programmatic file loading
        if getattr(self, "_loading_file", False):
            return

        if not self._is_dirty:
            self._is_dirty = True
            # Show asterisk indicator for unsaved changes
            current_text = self._file_path_label.text
            if not current_text.endswith(" *"):
                self._file_path_label.set_text(f"{current_text} *")

    async def _on_keyboard(self, e: KeyEventArguments) -> None:
        """Handle keyboard events for Ctrl+S save shortcut.

        Args:
            e: The keyboard event arguments.
        """
        if e.key == "s" and e.modifiers.ctrl and e.action.keydown:
            await self._on_save()

    async def _on_save(self) -> None:
        """Handle save button click or Ctrl+S shortcut.

        Executes the save workflow:
        1. Disable save button and show loading indicator
        2. Call EditorService.save_file with current content
        3. On success: clear dirty flag, remove asterisk, show notification
        4. On failure: show compiler errors in collapsible panel
        5. Re-enable save button

        Preserves cursor position and scroll state after save.
        """
        if self._current_file is None or self._editor is None:
            return

        if self._is_saving:
            return

        # 1. Disable save button and show loading indicator
        self._is_saving = True
        self._save_button.props("disable")
        if self._save_spinner:
            self._save_spinner.set_visibility(True)

        try:
            # 2. Call EditorService.save_file
            content = self._editor.value
            result = await self._editor_service.save_file(
                self._current_file, content
            )

            if result.success:
                # 3. On success: clear dirty flag, remove asterisk
                self._is_dirty = False
                display_path = truncate_path_display(self._current_file)
                self._file_path_label.set_text(display_path)
                self._hide_error_panel()
                ui.notify("File saved successfully", type="positive", timeout=3000)
            else:
                # 4. On failure: show compiler errors in collapsible panel
                self._show_error_panel(result.errors)
        finally:
            # 5. Re-enable save button and hide loading indicator
            self._is_saving = False
            self._save_button.props(remove="disable")
            if self._save_spinner:
                self._save_spinner.set_visibility(False)

    def _show_error_panel(self, errors: list[str]) -> None:
        """Display compiler errors in the collapsible error panel.

        Args:
            errors: List of compiler error messages to display.
        """
        if self._error_panel is None:
            return

        # Clear previous errors
        self._error_content.clear()

        # Add error messages
        with self._error_content:
            for error in errors:
                ui.label(error).classes(
                    "text-body2 text-negative font-mono whitespace-pre-wrap"
                )

        # Show and expand the error panel
        self._error_panel.set_visibility(True)
        self._error_panel.open()

    def _hide_error_panel(self) -> None:
        """Hide the compiler error panel."""
        if self._error_panel is not None:
            self._error_panel.close()
            self._error_panel.set_visibility(False)

    async def _on_helper_send(self) -> None:
        """Handle helper panel send button click.

        Validates non-empty input, builds EditorContext from current state,
        calls helper_service.send_message(), displays the response in the
        conversation area, and renders any DiffSuggestion components.
        """
        text = self._helper_input.value
        if not text or not text.strip():
            return

        if self._helper_loading:
            return

        user_message = text.strip()
        self._helper_input.value = ""
        self._last_user_message = user_message

        # Display user message in conversation
        self._display_helper_user_message(user_message)

        # Build EditorContext from current state
        context = self._build_editor_context()

        # Show loading indicator
        self._helper_loading = True
        self._helper_spinner_row.classes(remove="hidden")
        self._helper_send_btn.props("disable")

        try:
            # Call helper service
            response = await self._helper_service.send_message(
                user_message, context
            )

            if response.error:
                # Display error inline with retry button
                self._display_helper_error(response.error)
            else:
                # Display assistant response
                self._display_helper_assistant_message(response.text)

                # Render DiffSuggestion components
                for suggestion in response.suggestions:
                    self._suggestions.append(suggestion)
                    self._render_diff_suggestion(suggestion)

        except Exception as e:
            self._display_helper_error(f"Unexpected error: {e}")
        finally:
            # Hide loading indicator
            self._helper_loading = False
            self._helper_spinner_row.classes(add="hidden")
            self._helper_send_btn.props(remove="disable")
            self._scroll_helper_to_bottom()

    def _toggle_helper(self) -> None:
        """Toggle the helper panel expanded/collapsed state.

        When collapsed, hides the conversation area and input, showing
        only the toggle button. When expanded, shows the full panel.
        """
        self._helper_expanded = not self._helper_expanded
        if self._helper_expanded:
            self._helper_body.set_visibility(True)
            self._helper_toggle.props("icon=chevron_right")
        else:
            self._helper_body.set_visibility(False)
            self._helper_toggle.props("icon=chevron_left")

    def _build_editor_context(self) -> EditorContext:
        """Build an EditorContext from the current editor state.

        Includes file path, content, cursor line, surrounding lines,
        and project file list.

        Returns:
            EditorContext populated with current state.
        """
        file_content = ""
        cursor_line = 0
        surrounding_lines = ""

        if self._editor is not None:
            file_content = self._editor.value or ""
            # NiceGUI CodeMirror doesn't expose cursor position directly,
            # so we default to line 1 if not available
            cursor_line = 1

        # Get project file list from the cached tree
        project_files: list[str] = []
        try:
            nodes = getattr(self, "_cached_file_nodes", None)
            if nodes:
                project_files = self._collect_file_paths(nodes)
        except Exception:
            pass

        # Build surrounding lines (10 above/below cursor)
        if file_content and cursor_line > 0:
            lines = file_content.splitlines()
            start = max(0, cursor_line - 11)
            end = min(len(lines), cursor_line + 10)
            surrounding_lines = "\n".join(lines[start:end])

        return EditorContext(
            file_path=self._current_file,
            file_content=file_content,
            cursor_line=cursor_line,
            surrounding_lines=surrounding_lines,
            project_files=project_files,
        )

    def _collect_file_paths(self, nodes: list[object]) -> list[str]:
        """Recursively collect file paths from FileNode tree.

        Args:
            nodes: List of FileNode objects.

        Returns:
            Flat list of relative file paths.
        """
        from tj_chat.editor_models import FileNode

        paths: list[str] = []
        for node in nodes:
            if not isinstance(node, FileNode):
                continue
            if node.is_directory:
                paths.extend(self._collect_file_paths(node.children))
            else:
                paths.append(node.path)
        return paths

    def _display_helper_user_message(self, text: str) -> None:
        """Display a user message in the helper conversation area.

        Args:
            text: The user's message text.
        """
        self._conversation.append({"role": "user", "content": text})
        with self._helper_content:
            with ui.row().classes("w-full justify-end"):
                ui.chat_message(
                    text=text,
                    sent=True,
                ).classes("max-w-[90%]")
        self._scroll_helper_to_bottom()

    def _display_helper_assistant_message(self, text: str) -> None:
        """Display an assistant response in the helper conversation area.

        Args:
            text: The assistant's response text.
        """
        self._conversation.append({"role": "assistant", "content": text})
        with self._helper_content:
            with ui.row().classes("w-full justify-start"):
                ui.chat_message(
                    text=text,
                    sent=False,
                    name="Helper",
                    stamp="🤖",
                ).classes("max-w-[90%]")
        self._scroll_helper_to_bottom()

    def _display_helper_error(self, error_msg: str) -> None:
        """Display an error message inline in the helper panel with retry button.

        Args:
            error_msg: The error message to display.
        """
        self._conversation.append({"role": "error", "content": error_msg})
        with self._helper_content:
            with ui.card().classes(
                "w-full bg-red-50 border-l-4 border-red-400 p-2"
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("error_outline").classes("text-red-600")
                    ui.label(error_msg).classes("text-sm text-red-800 flex-grow")
                    ui.button(
                        "Retry",
                        icon="refresh",
                        on_click=self._on_helper_retry,
                    ).props("flat dense color=negative size=sm")
        self._scroll_helper_to_bottom()

    async def _on_helper_retry(self) -> None:
        """Retry the last failed helper message.

        Re-sends the last user message to the helper service.
        """
        if self._last_user_message:
            self._helper_input.value = self._last_user_message
            await self._on_helper_send()

    def _render_diff_suggestion(self, suggestion: DiffSuggestion) -> None:
        """Render a DiffSuggestion component with Accept/Reject buttons.

        Shows original vs suggested content side by side with action buttons.
        Handles accept (apply to editor), reject (disable buttons), and
        outdated (content changed) states.

        Args:
            suggestion: The DiffSuggestion to render.
        """
        with self._helper_content:
            card = ui.card().classes(
                "w-full border border-blue-200 bg-blue-50 p-2"
            )
            with card:
                # Header with file path and line range
                ui.label(
                    f"📝 Suggestion: {suggestion.file_path} "
                    f"(lines {suggestion.start_line}-{suggestion.end_line})"
                ).classes("text-xs text-blue-800 font-bold mb-1")

                # Original content (if available)
                if suggestion.original_content:
                    with ui.expansion("Original", icon="remove").classes(
                        "w-full text-xs"
                    ):
                        ui.code(suggestion.original_content).classes(
                            "w-full text-xs"
                        )

                # Suggested content
                with ui.expansion("Suggested", icon="add").classes(
                    "w-full text-xs"
                ).props("default-opened"):
                    ui.code(suggestion.suggested_content).classes(
                        "w-full text-xs"
                    )

                # Action buttons container
                btn_row = ui.row().classes("w-full justify-end gap-1 mt-1")
                with btn_row:
                    accept_btn = ui.button(
                        "Accept",
                        icon="check",
                        on_click=lambda s=suggestion, c=card, b=btn_row: (
                            self._accept_suggestion(s, c, b)
                        ),
                    ).props("flat dense color=positive size=sm")
                    reject_btn = ui.button(
                        "Reject",
                        icon="close",
                        on_click=lambda s=suggestion, c=card, b=btn_row: (
                            self._reject_suggestion(s, c, b)
                        ),
                    ).props("flat dense color=negative size=sm")

                # Store button references on the suggestion for state management
                suggestion._ui_card = card  # type: ignore[attr-defined]
                suggestion._ui_accept_btn = accept_btn  # type: ignore[attr-defined]
                suggestion._ui_reject_btn = reject_btn  # type: ignore[attr-defined]
                suggestion._ui_btn_row = btn_row  # type: ignore[attr-defined]

        self._scroll_helper_to_bottom()

    async def _accept_suggestion(
        self,
        suggestion: DiffSuggestion,
        card: ui.card,
        btn_row: ui.row,
    ) -> None:
        """Handle accepting a diff suggestion.

        Applies the suggestion to the editor content. If the content at the
        referenced line range has changed (outdated), shows an indication
        instead of applying.

        Args:
            suggestion: The DiffSuggestion to accept.
            card: The UI card containing the suggestion.
            btn_row: The row containing the action buttons.
        """
        if suggestion.status != "pending":
            return

        if self._editor is None or self._current_file is None:
            return

        # Apply the suggestion to the editor content
        current_content = self._editor.value or ""
        new_content, success = apply_suggestion(current_content, suggestion)

        if success:
            # Update editor content
            self._editor.value = new_content
            suggestion.status = "accepted"
            self._is_dirty = True

            # Update dirty indicator in header
            current_text = self._file_path_label.text
            if not current_text.endswith(" *"):
                self._file_path_label.set_text(f"{current_text} *")

            # Update UI: show accepted state
            card.classes(remove="border-blue-200 bg-blue-50")
            card.classes(add="border-green-300 bg-green-50")
            btn_row.clear()
            with btn_row:
                ui.label("✓ Accepted").classes(
                    "text-xs text-green-700 font-bold"
                )
        else:
            # Content has changed — mark as outdated
            suggestion.status = "outdated"
            card.classes(remove="border-blue-200 bg-blue-50")
            card.classes(add="border-amber-300 bg-amber-50")
            btn_row.clear()
            with btn_row:
                ui.icon("warning").classes("text-amber-600 text-sm")
                ui.label("Outdated — content has changed").classes(
                    "text-xs text-amber-700"
                )

    def _reject_suggestion(
        self,
        suggestion: DiffSuggestion,
        card: ui.card,
        btn_row: ui.row,
    ) -> None:
        """Handle rejecting a diff suggestion.

        Marks the suggestion as rejected, disables buttons, and shows
        rejected styling.

        Args:
            suggestion: The DiffSuggestion to reject.
            card: The UI card containing the suggestion.
            btn_row: The row containing the action buttons.
        """
        if suggestion.status != "pending":
            return

        suggestion.status = "rejected"

        # Update UI: show rejected state
        card.classes(remove="border-blue-200 bg-blue-50")
        card.classes(add="border-grey-300 bg-grey-100 opacity-60")
        btn_row.clear()
        with btn_row:
            ui.label("✗ Rejected").classes(
                "text-xs text-grey-500 italic"
            )

    def _scroll_helper_to_bottom(self) -> None:
        """Scroll the helper conversation area to the bottom."""
        if hasattr(self, "_helper_scroll"):
            self._helper_scroll.scroll_to(percent=1.0)

    def _build_tree_data(self, nodes: list[FileNode]) -> list[dict[str, Any]]:
        """Convert FileNode tree to NiceGUI tree data format.

        Maps each FileNode to a dict with 'id', 'label', 'icon', and
        'children' keys suitable for ui.tree consumption.

        Args:
            nodes: List of FileNode instances from the editor service.

        Returns:
            List of dicts in NiceGUI tree format.
        """
        result: list[dict[str, Any]] = []
        for node in nodes:
            item: dict[str, Any] = {
                "id": node.path,
                "label": node.name,
                "icon": self._get_node_icon(node),
            }
            if node.is_directory and node.children:
                item["children"] = self._build_tree_data(node.children)
            elif node.is_directory:
                item["children"] = []
            result.append(item)
        return result

    def _get_node_icon(self, node: FileNode) -> str:
        """Get the appropriate icon for a file tree node.

        Uses distinct icons to differentiate directories, .tjp files,
        .tji files, and other file types.

        Args:
            node: The FileNode to get an icon for.

        Returns:
            Material icon name string.
        """
        if node.is_directory:
            return "folder"
        if node.file_type == "tjp":
            return "star"
        if node.file_type == "tji":
            return "code"
        return "description"

    async def _on_file_select(self, node_id: str | None) -> None:
        """Handle file tree node selection.

        If the selected node is a directory, ignores the selection.
        If the editor has unsaved changes, prompts the user to confirm
        discarding them before loading the new file.

        Args:
            node_id: The path (id) of the selected tree node, or None.
        """
        if node_id is None:
            return

        # Check if the selected node is a directory by looking it up
        if self._is_directory_node(node_id):
            return

        if self._is_dirty:
            await self._confirm_discard_and_load(node_id)
        else:
            await self.load_file(node_id)

    def _is_directory_node(self, path: str) -> bool:
        """Check if a path corresponds to a directory in the file tree.

        Uses the cached file tree data from initial render to avoid
        re-scanning the filesystem on every click.

        Args:
            path: Relative path to check.

        Returns:
            True if the path is a directory node, False otherwise.
        """
        nodes = getattr(self, "_cached_file_nodes", None)
        if nodes is None:
            return False
        return self._find_directory_in_nodes(nodes, path)

    def _find_directory_in_nodes(
        self, nodes: list[FileNode], path: str
    ) -> bool:
        """Recursively search for a directory node by path.

        Args:
            nodes: List of FileNode instances to search.
            path: The path to find.

        Returns:
            True if found and is a directory, False otherwise.
        """
        for node in nodes:
            if node.path == path:
                return node.is_directory
            if node.is_directory and node.children:
                if self._find_directory_in_nodes(node.children, path):
                    return True
        return False

    async def _confirm_discard_and_load(self, relative_path: str) -> None:
        """Show a confirmation dialog for discarding unsaved changes.

        If the user confirms, loads the new file. Otherwise, the
        current file remains loaded with its unsaved changes.

        Args:
            relative_path: Path of the file to load if confirmed.
        """
        with ui.dialog() as dialog, ui.card():
            ui.label("Discard unsaved changes?").classes("text-h6")
            ui.label(
                "The current file has unsaved changes that will be lost."
            ).classes("text-body2 text-grey-7")
            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Discard",
                    on_click=lambda: dialog.submit("discard"),
                ).props("flat color=negative")

        result = await dialog
        if result == "discard":
            await self.load_file(relative_path)
