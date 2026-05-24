"""Reads TaskJuggler project files and extracts structured information.

Parses .tjp and .tji files to provide project summaries, task/resource
listings, and similarity-based search functionality.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from tj_chat.models import (
    ProjectSummary,
    ResourceInfo,
    ResourceMatch,
    TaskInfo,
    TaskMatch,
)

# Regex for parsing end date from task blocks (e.g. "end 2024-03-15")
_END_DATE_RE = re.compile(r'end\s+(\d{4}-\d{2}-\d{2})')
# Regex for parsing complete percentage (e.g. "complete 75")
_COMPLETE_RE = re.compile(r'complete\s+(\d+)')


class ProjectReader:
    """Reads TaskJuggler project files and extracts structured information."""

    def __init__(self, project_dir: Path) -> None:
        """Initialize the project reader.

        Args:
            project_dir: Path to the project directory containing .tjp and .tji files.
        """
        self._project_dir = project_dir

    def get_project_summary(self) -> ProjectSummary:
        """Parse project metadata and return a structured summary.

        Extracts project name, dates, file tree, resources, and top-level tasks
        from the .tjp and .tji files.

        Returns:
            ProjectSummary with project metadata.
        """
        project_name = ""
        start_date = ""
        end_date = ""
        now_date = ""

        # Parse the main .tjp file for project metadata
        tjp_files = list(self._project_dir.glob("*.tjp"))
        for tjp_file in tjp_files:
            content = tjp_file.read_text(encoding="utf-8")
            project_match = re.search(
                r'project\s+\w+\s+"([^"]+)"\s+(\S+)\s+(\S+)',
                content,
            )
            if project_match:
                project_name = project_match.group(1)
                start_date = project_match.group(2)
                end_duration = project_match.group(3)
                # end_date could be a duration like +26w or an actual date
                end_date = end_duration

            now_match = re.search(r'now\s+(\S+)', content)
            if now_match:
                now_date = now_match.group(1)

        file_tree = self.get_file_tree()
        resources = self.list_resources()
        resource_ids = [r.id for r in resources]

        tasks = self.list_tasks()
        # Top-level tasks are those with only one dot-segment (direct children of root)
        top_level_tasks = [t.name for t in tasks if t.path.count(".") == 1]

        return ProjectSummary(
            project_name=project_name,
            start_date=start_date,
            end_date=end_date,
            now_date=now_date,
            file_tree=file_tree,
            resource_ids=resource_ids,
            top_level_tasks=top_level_tasks,
        )

    def list_tasks(self) -> list[TaskInfo]:
        """Extract all tasks from project .tji files.

        Returns:
            List of TaskInfo objects with path, name, effort, allocations,
            dependencies, and milestone status.
        """
        tasks: list[TaskInfo] = []
        # Look for task definitions in all .tji files
        for tji_file in self._iter_tji_files():
            content = tji_file.read_text(encoding="utf-8")
            tasks.extend(self._parse_tasks(content))
        return tasks

    def list_resources(self) -> list[ResourceInfo]:
        """Extract all resources from project .tji files.

        Returns:
            List of ResourceInfo objects with id, name, rate, and working hours.
        """
        resources: list[ResourceInfo] = []
        for tji_file in self._iter_tji_files():
            content = tji_file.read_text(encoding="utf-8")
            resources.extend(self._parse_resources(content))
        return resources

    def find_task(self, query: str) -> list[TaskMatch]:
        """Find tasks matching a query using similarity search.

        Uses difflib.SequenceMatcher for fuzzy matching against task paths
        and names. Returns at most 5 results ordered by decreasing score.

        Args:
            query: Search string to match against task paths and names.

        Returns:
            List of TaskMatch objects (max 5) ordered by decreasing score.
        """
        tasks = self.list_tasks()
        scored: list[TaskMatch] = []

        query_lower = query.lower()
        for task in tasks:
            # Score against both path and name, take the best
            path_score = SequenceMatcher(None, query_lower, task.path.lower()).ratio()
            name_score = SequenceMatcher(None, query_lower, task.name.lower()).ratio()
            score = max(path_score, name_score)
            if score > 0.0:
                scored.append(TaskMatch(task=task, score=score))

        # Sort by decreasing score
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:5]

    def find_resource(self, query: str) -> list[ResourceMatch]:
        """Find resources matching a query using similarity search.

        Checks for exact ID/name match first, then falls back to fuzzy matching.
        Returns at most 5 results ordered by score (exact matches first).

        Args:
            query: Search string to match against resource IDs and names.

        Returns:
            List of ResourceMatch objects (max 5) ordered by relevance.
        """
        resources = self.list_resources()
        matches: list[tuple[float, ResourceMatch]] = []

        query_lower = query.lower()
        for resource in resources:
            # Check for exact match on ID or name
            if query_lower == resource.id.lower() or query_lower == resource.name.lower():
                matches.append((1.0, ResourceMatch(resource=resource, exact=True)))
            else:
                # Fuzzy match against both id and name
                id_score = SequenceMatcher(None, query_lower, resource.id.lower()).ratio()
                name_score = SequenceMatcher(None, query_lower, resource.name.lower()).ratio()
                score = max(id_score, name_score)
                if score > 0.0:
                    matches.append((score, ResourceMatch(resource=resource, exact=False)))

        # Sort by decreasing score
        matches.sort(key=lambda m: m[0], reverse=True)
        return [m[1] for m in matches[:5]]

    def get_file_tree(self) -> list[str]:
        """List project directory contents as relative paths.

        Returns:
            List of relative file paths within the project directory.
        """
        if not self._project_dir.exists():
            return []

        files: list[str] = []
        for path in sorted(self._project_dir.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                relative = path.relative_to(self._project_dir)
                files.append(str(relative).replace("\\", "/"))
        return files

    def _iter_tji_files(self) -> list[Path]:
        """Iterate over all .tji files in the project directory tree.

        Returns:
            List of Path objects for all .tji files found.
        """
        if not self._project_dir.exists():
            return []
        return sorted(self._project_dir.rglob("*.tji"))

    def _parse_tasks(self, content: str) -> list[TaskInfo]:
        """Parse task definitions from TaskJuggler file content.

        Handles nested task hierarchies and extracts effort, allocations,
        dependencies, and milestone markers.

        Args:
            content: Raw text content of a .tji file.

        Returns:
            List of TaskInfo objects parsed from the content.
        """
        tasks: list[TaskInfo] = []
        # Remove block comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        # Remove line comments
        content = re.sub(r'#[^\n]*', '', content)

        self._parse_task_block(content, [], tasks)
        return tasks

    def _parse_task_block(
        self, content: str, parent_path: list[str], tasks: list[TaskInfo]
    ) -> None:
        """Recursively parse task blocks from content.

        Args:
            content: Text content to parse for task definitions.
            parent_path: List of parent task IDs forming the path prefix.
            tasks: Accumulator list to append found tasks to.
        """
        # Find task definitions at this level
        # Pattern: task <id> "<name>" { ... }
        pos = 0
        while pos < len(content):
            task_match = re.search(r'task\s+(\w+)\s+"([^"]+)"\s*\{', content[pos:])
            if not task_match:
                break

            task_id = task_match.group(1)
            task_name = task_match.group(2)
            block_start = pos + task_match.end()

            # Find the matching closing brace
            block_content = self._extract_block(content, block_start)
            if block_content is None:
                break

            full_path = ".".join([*parent_path, task_id])

            # Extract task attributes from the block
            effort = self._extract_effort(block_content)
            allocations = self._extract_allocations(block_content)
            dependencies = self._extract_dependencies(block_content)
            is_milestone = "milestone" in block_content and not re.search(
                r'task\s+\w+\s+"[^"]*".*?milestone', block_content, re.DOTALL
            )
            # More precise milestone check: milestone keyword at this level
            is_milestone = self._is_milestone(block_content)
            end_date = self._extract_end_date(block_content)
            complete = self._extract_complete(block_content)

            tasks.append(
                TaskInfo(
                    path=full_path,
                    name=task_name,
                    effort=effort,
                    allocations=allocations,
                    dependencies=dependencies,
                    is_milestone=is_milestone,
                    end_date=end_date,
                    complete=complete,
                )
            )

            # Recursively parse nested tasks
            self._parse_task_block(block_content, [*parent_path, task_id], tasks)

            # Move past this block
            pos = block_start + len(block_content) + 1  # +1 for closing brace

    def _extract_block(self, content: str, start: int) -> str | None:
        """Extract content between matching braces starting at position.

        Args:
            content: Full text content.
            start: Position right after the opening brace.

        Returns:
            The text between the braces, or None if no matching brace found.
        """
        depth = 1
        pos = start
        while pos < len(content) and depth > 0:
            if content[pos] == "{":
                depth += 1
            elif content[pos] == "}":
                depth -= 1
            pos += 1
        if depth == 0:
            return content[start : pos - 1]
        return None

    def _extract_effort(self, block: str) -> str | None:
        """Extract effort value from a task block.

        Args:
            block: Task block content.

        Returns:
            Effort string (e.g., "5d", "10h") or None if not found.
        """
        # Only match effort at this level (not inside nested task blocks)
        # Remove nested task blocks first
        clean = self._remove_nested_tasks(block)
        match = re.search(r'effort\s+(\S+)', clean)
        return match.group(1) if match else None

    def _extract_allocations(self, block: str) -> list[str]:
        """Extract resource allocations from a task block.

        Args:
            block: Task block content.

        Returns:
            List of resource IDs allocated to this task.
        """
        clean = self._remove_nested_tasks(block)
        allocations: list[str] = []
        for match in re.finditer(r'allocate\s+(.+)', clean):
            line_content = match.group(1).strip()
            # Handle "allocate alice" and "allocate alice, bob"
            ids = [r.strip() for r in line_content.split(",") if r.strip()]
            for resource_id in ids:
                # Take only the first word (resource ID)
                first_word = resource_id.split()[0]
                if first_word and first_word not in allocations:
                    allocations.append(first_word)
        return allocations

    def _extract_dependencies(self, block: str) -> list[str]:
        """Extract task dependencies from a task block.

        Args:
            block: Task block content.

        Returns:
            List of dependency path strings.
        """
        clean = self._remove_nested_tasks(block)
        dependencies: list[str] = []
        for match in re.finditer(r'depends\s+(.+)', clean):
            deps_str = match.group(1).strip()
            # Dependencies can be comma-separated
            for dep in deps_str.split(","):
                dep = dep.strip()
                if dep:
                    dependencies.append(dep)
        return dependencies

    def _is_milestone(self, block: str) -> bool:
        """Check if a task block defines a milestone.

        Only checks at the current level (not in nested tasks).

        Args:
            block: Task block content.

        Returns:
            True if the task is a milestone.
        """
        clean = self._remove_nested_tasks(block)
        return bool(re.search(r'\bmilestone\b', clean))

    def _extract_end_date(self, block: str) -> str | None:
        """Extract planned end date from a task block.

        Args:
            block: Task block content.

        Returns:
            End date string in YYYY-MM-DD format, or None if not found.
        """
        clean = self._remove_nested_tasks(block)
        match = _END_DATE_RE.search(clean)
        return match.group(1) if match else None

    def _extract_complete(self, block: str) -> int | None:
        """Extract completion percentage from a task block.

        Args:
            block: Task block content.

        Returns:
            Completion percentage (0-100), or None if not found.
        """
        clean = self._remove_nested_tasks(block)
        match = _COMPLETE_RE.search(clean)
        return int(match.group(1)) if match else None

    def _remove_nested_tasks(self, block: str) -> str:
        """Remove nested task blocks from content to parse only current level.

        Args:
            block: Task block content potentially containing nested tasks.

        Returns:
            Content with nested task blocks removed.
        """
        result = []
        pos = 0
        while pos < len(block):
            task_match = re.search(r'task\s+\w+\s+"[^"]*"\s*\{', block[pos:])
            if not task_match:
                result.append(block[pos:])
                break
            # Add content before the nested task
            result.append(block[pos : pos + task_match.start()])
            # Skip the nested task block
            block_start = pos + task_match.end()
            nested_content = self._extract_block(block, block_start)
            if nested_content is None:
                result.append(block[pos:])
                break
            pos = block_start + len(nested_content) + 1  # +1 for closing brace
        return "".join(result)

    def _parse_resources(self, content: str) -> list[ResourceInfo]:
        """Parse resource definitions from TaskJuggler file content.

        Args:
            content: Raw text content of a .tji file.

        Returns:
            List of ResourceInfo objects parsed from the content.
        """
        resources: list[ResourceInfo] = []
        # Remove block comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        # Remove line comments
        content = re.sub(r'#[^\n]*', '', content)

        # Find resource definitions: resource <id> "<name>" { ... }
        for match in re.finditer(r'resource\s+(\w+)\s+"([^"]+)"\s*\{', content):
            resource_id = match.group(1)
            resource_name = match.group(2)
            block_start = match.end()

            block_content = self._extract_block(content, block_start)
            if block_content is None:
                continue

            # Extract rate
            rate: float | None = None
            rate_match = re.search(r'rate\s+([\d.]+)', block_content)
            if rate_match:
                rate = float(rate_match.group(1))

            # Extract working hours (first workinghours line)
            working_hours: str | None = None
            wh_match = re.search(r'workinghours\s+(.+)', block_content)
            if wh_match:
                working_hours = wh_match.group(1).strip()

            resources.append(
                ResourceInfo(
                    id=resource_id,
                    name=resource_name,
                    rate=rate,
                    working_hours=working_hours,
                )
            )

        return resources
