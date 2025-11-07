"""Validation helpers for Shannot.

This module provides validation utilities to replace Pydantic functionality
while keeping code DRY and maintaining type safety.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar, get_args, get_origin

T = TypeVar("T")


class ValidationError(Exception):
    """Raised when validation fails.

    This replaces pydantic.ValidationError with a simpler implementation.
    """

    def __init__(self, message: str, field: str | None = None):
        """Initialize validation error.

        Args:
            message: Error message
            field: Optional field name that failed validation
        """
        self.field = field
        if field:
            super().__init__(f"{field}: {message}")
        else:
            super().__init__(message)


def validate_type(value: Any, expected_type: type[T], field_name: str) -> T:
    """Validate that a value matches the expected type.

    Args:
        value: Value to validate
        expected_type: Expected type
        field_name: Name of field being validated (for error messages)

    Returns:
        The validated value

    Raises:
        ValidationError: If validation fails
    """
    # Handle None for optional types
    if value is None:
        origin = get_origin(expected_type)
        if origin is type(None) or (
            hasattr(expected_type, "__args__") and type(None) in get_args(expected_type)
        ):
            return value  # type: ignore[return-value]

    # Handle Union types (e.g., str | None)
    origin = get_origin(expected_type)
    if origin is type(None):
        args = get_args(expected_type)
        if len(args) == 2 and type(None) in args:
            # This is Optional[T]
            actual_type = args[0] if args[1] is type(None) else args[1]
            if value is None:
                return value  # type: ignore[return-value]
            expected_type = actual_type  # type: ignore[assignment]

    # Handle basic types
    if not isinstance(value, expected_type):
        raise ValidationError(
            f"expected {expected_type.__name__}, got {type(value).__name__}",
            field_name,
        )

    return value  # type: ignore[return-value]


def validate_literal(value: Any, allowed_values: tuple[Any, ...], field_name: str) -> Any:
    """Validate that a value is one of the allowed literal values.

    Args:
        value: Value to validate
        allowed_values: Tuple of allowed values
        field_name: Name of field being validated

    Returns:
        The validated value

    Raises:
        ValidationError: If value not in allowed_values
    """
    if value not in allowed_values:
        allowed_str = ", ".join(repr(v) for v in allowed_values)
        raise ValidationError(
            f"must be one of {allowed_str}, got {value!r}",
            field_name,
        )
    return value


def validate_path(value: str | Path | None, field_name: str, expand: bool = True) -> Path | None:
    """Validate and normalize a path.

    Args:
        value: Path to validate
        field_name: Name of field being validated
        expand: Whether to expand ~ to home directory

    Returns:
        Normalized Path object, or None if value is None

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        return None

    if not isinstance(value, (str, Path)):
        raise ValidationError(
            f"expected str or Path, got {type(value).__name__}",
            field_name,
        )

    path = Path(value)
    if expand:
        path = path.expanduser()

    return path


def validate_list_of_strings(value: Any, field_name: str) -> list[str]:
    """Validate that a value is a list of strings.

    Args:
        value: Value to validate
        field_name: Name of field being validated

    Returns:
        The validated list

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(value, list):
        raise ValidationError(
            f"expected list, got {type(value).__name__}",
            field_name,
        )

    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise ValidationError(
                f"expected list of strings, but item {i} is {type(item).__name__}",
                field_name,
            )

    return value


def validate_dict_of_type(
    value: Any,
    key_type: type,
    value_type: type,
    field_name: str,
) -> dict[Any, Any]:
    """Validate that a value is a dict with specific key/value types.

    Args:
        value: Value to validate
        key_type: Expected type for keys
        value_type: Expected type for values
        field_name: Name of field being validated

    Returns:
        The validated dict

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(value, dict):
        raise ValidationError(
            f"expected dict, got {type(value).__name__}",
            field_name,
        )

    for k, v in value.items():
        if not isinstance(k, key_type):
            raise ValidationError(
                f"expected dict keys of type {key_type.__name__}, got {type(k).__name__}",
                field_name,
            )
        if not isinstance(v, value_type):
            raise ValidationError(
                f"expected dict values of type {value_type.__name__}, got {type(v).__name__}",
                field_name,
            )

    return value


def validate_int_range(
    value: Any, field_name: str, min_val: int | None = None, max_val: int | None = None
) -> int:
    """Validate that a value is an integer within a range.

    Args:
        value: Value to validate
        field_name: Name of field being validated
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)

    Returns:
        The validated integer

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(
            f"expected int, got {type(value).__name__}",
            field_name,
        )

    if min_val is not None and value < min_val:
        raise ValidationError(
            f"must be >= {min_val}, got {value}",
            field_name,
        )

    if max_val is not None and value > max_val:
        raise ValidationError(
            f"must be <= {max_val}, got {value}",
            field_name,
        )

    return value


def validate_bool(value: Any, field_name: str) -> bool:
    """Validate that a value is a boolean.

    Args:
        value: Value to validate
        field_name: Name of field being validated

    Returns:
        The validated boolean

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(value, bool):
        raise ValidationError(
            f"expected bool, got {type(value).__name__}",
            field_name,
        )
    return value


def validate_command(value: Any, field_name: str) -> list[str]:
    """Validate a command array (non-empty list of strings).

    Args:
        value: Value to validate
        field_name: Name of field being validated

    Returns:
        The validated command list

    Raises:
        ValidationError: If validation fails
    """
    validated = validate_list_of_strings(value, field_name)
    if not validated:
        raise ValidationError("must not be empty", field_name)
    return validated


def validate_port(value: Any, field_name: str) -> int:
    """Validate a network port number (1-65535).

    Args:
        value: Value to validate
        field_name: Name of field being validated

    Returns:
        The validated port number

    Raises:
        ValidationError: If validation fails
    """
    return validate_int_range(value, field_name, min_val=1, max_val=65535)


def validate_timeout(value: Any, field_name: str, max_val: int = 3600) -> int:
    """Validate a timeout value in seconds.

    Args:
        value: Value to validate
        field_name: Name of field being validated
        max_val: Maximum allowed timeout (default: 3600 seconds / 1 hour)

    Returns:
        The validated timeout

    Raises:
        ValidationError: If validation fails
    """
    return validate_int_range(value, field_name, min_val=1, max_val=max_val)


def validate_safe_path(value: Any, field_name: str) -> str:
    """Validate a path is safe (no path traversal attacks).

    This function checks for common path traversal patterns that could
    allow access to files outside the intended directory.

    Args:
        value: Value to validate (path string)
        field_name: Name of field being validated

    Returns:
        The validated path string

    Raises:
        ValidationError: If path contains dangerous patterns

    Security Checks:
        - No ".." components (directory traversal)
        - No null bytes (C string termination attacks)
        - No newlines (command injection in some contexts)
        - Must be a non-empty string

    Example:
        >>> validate_safe_path("/etc/hosts", "path")  # OK
        '/etc/hosts'
        >>> validate_safe_path("../../../etc/passwd", "path")  # FAIL
        ValidationError: path: contains path traversal pattern '..'
    """
    # First validate it's a non-empty string
    validated_str = validate_type(value, str, field_name)
    if not validated_str:
        raise ValidationError("must be non-empty", field_name)

    # Check for path traversal
    if ".." in validated_str:
        raise ValidationError("contains path traversal pattern '..'", field_name)

    # Check for null bytes (security issue)
    if "\0" in validated_str:
        raise ValidationError("contains null byte", field_name)

    # Check for newlines (potential command injection)
    if "\n" in validated_str or "\r" in validated_str:
        raise ValidationError("contains newline character", field_name)

    return validated_str


__all__ = [
    "ValidationError",
    "validate_type",
    "validate_literal",
    "validate_path",
    "validate_list_of_strings",
    "validate_dict_of_type",
    "validate_int_range",
    "validate_bool",
    "validate_command",
    "validate_port",
    "validate_timeout",
    "validate_safe_path",
]
