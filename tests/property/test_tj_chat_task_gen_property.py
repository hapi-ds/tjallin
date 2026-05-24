"""Property-based tests for TaskJuggler task generation.

**Validates: Requirements 3.2**

Property 18: Task generation includes required attributes.
- For any valid TaskRequest specifying a task ID, name, effort, and allocation,
  the generated TaskJuggler task definition SHALL contain the task ID, the task
  name as a quoted string, an effort line, and an allocate line.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.generators import TaskGenerator
from tj_chat.models import TaskRequest

# Strategy for valid TaskJuggler identifiers (alphanumeric + underscore, starts with letter)
_tj_id_char = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyz_0123456789"
)
_tj_id = st.builds(
    lambda first, rest: first + rest,
    first=st.sampled_from("abcdefghijklmnopqrstuvwxyz"),
    rest=st.text(alphabet=_tj_id_char, min_size=1, max_size=20),
)

# Strategy for task names (non-empty, no unescaped double quotes)
_task_name = st.text(
    alphabet=st.characters(exclude_characters='"\x00'),
    min_size=1,
    max_size=60,
).filter(lambda s: s.strip() != "")

# Strategy for effort values (e.g., "5d", "40h", "2w", "3m")
_effort_unit = st.sampled_from(["h", "d", "w", "m"])
_effort_value = st.builds(
    lambda num, unit: f"{num}{unit}",
    num=st.integers(min_value=1, max_value=100),
    unit=_effort_unit,
)

# Strategy for resource IDs used in allocation
_resource_id = _tj_id


@st.composite
def valid_task_request(draw: st.DrawFn) -> TaskRequest:
    """Generate a valid TaskRequest with all required fields."""
    task_id = draw(_tj_id)
    name = draw(_task_name)
    effort = draw(_effort_value)

    # Allocation can be a single string or a list of strings
    use_list = draw(st.booleans())
    if use_list:
        allocation = draw(st.lists(_resource_id, min_size=1, max_size=4))
    else:
        allocation = draw(_resource_id)

    return TaskRequest(
        task_id=task_id,
        name=name,
        effort=effort,
        allocation=allocation,
    )


class TestTaskGenerationIncludesRequiredAttributes:
    """Property 18: Task generation includes required attributes.

    **Validates: Requirements 3.2**
    """

    @given(task_req=valid_task_request())
    @settings(max_examples=200)
    def test_output_contains_task_id(self, task_req: TaskRequest) -> None:
        """Generated task definition contains the task ID."""
        generator = TaskGenerator()
        output = generator.generate(task_req)

        assert f"task {task_req.task_id}" in output

    @given(task_req=valid_task_request())
    @settings(max_examples=200)
    def test_output_contains_task_name_as_quoted_string(
        self, task_req: TaskRequest
    ) -> None:
        """Generated task definition contains the task name as a quoted string."""
        generator = TaskGenerator()
        output = generator.generate(task_req)

        assert f'"{task_req.name}"' in output

    @given(task_req=valid_task_request())
    @settings(max_examples=200)
    def test_output_contains_effort_line(self, task_req: TaskRequest) -> None:
        """Generated task definition contains an effort line with the specified value."""
        generator = TaskGenerator()
        output = generator.generate(task_req)

        assert f"effort {task_req.effort}" in output

    @given(task_req=valid_task_request())
    @settings(max_examples=200)
    def test_output_contains_allocate_line(self, task_req: TaskRequest) -> None:
        """Generated task definition contains allocate line(s) for all specified resources."""
        generator = TaskGenerator()
        output = generator.generate(task_req)

        if isinstance(task_req.allocation, list):
            for resource_id in task_req.allocation:
                assert f"allocate {resource_id}" in output
        else:
            assert f"allocate {task_req.allocation}" in output

    @given(task_req=valid_task_request())
    @settings(max_examples=200)
    def test_output_contains_all_required_attributes(
        self, task_req: TaskRequest
    ) -> None:
        """Generated task definition contains all four required attributes together."""
        generator = TaskGenerator()
        output = generator.generate(task_req)

        # Task ID on opening line
        assert f"task {task_req.task_id}" in output
        # Name as quoted string
        assert f'"{task_req.name}"' in output
        # Effort line
        assert f"effort {task_req.effort}" in output
        # At least one allocate line
        assert "allocate " in output
