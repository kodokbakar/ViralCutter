"""CLI argument validation helpers for ViralCutter pipeline."""
import os


def validate_batch_size(value):
    """Validate WhisperX batch size. Must be >= 1."""
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"Batch size must be an integer, got {type(value).__name__}")
    if value < 1:
        raise ValueError(f"Batch size must be >= 1, got {value}")
    return value


def validate_chunk_size(value, min_val=100):
    """Validate WhisperX chunk size. Must be >= min_val."""
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"Chunk size must be an integer, got {type(value).__name__}")
    if value < min_val:
        raise ValueError(f"Chunk size must be >= {min_val}, got {value}")
    return value


def validate_duration_range(min_dur, max_dur):
    """Validate min/max duration range."""
    if min_dur is None or max_dur is None:
        return
    if not isinstance(min_dur, int) or not isinstance(max_dur, int):
        raise ValueError("Duration values must be integers")
    if min_dur < 1:
        raise ValueError(f"Minimum duration must be >= 1, got {min_dur}")
    if max_dur < 1:
        raise ValueError(f"Maximum duration must be >= 1, got {max_dur}")
    if min_dur > max_dur:
        raise ValueError(
            f"Minimum duration ({min_dur}) exceeds maximum duration ({max_dur})"
        )


def validate_project_path(path):
    """Validate project path exists."""
    if path is None:
        return
    if not isinstance(path, str):
        raise ValueError(f"Project path must be a string, got {type(path).__name__}")
    if not os.path.exists(path):
        raise ValueError(f"Project path does not exist: {path}")


def validate_args(args):
    """Validate all CLI args. Raises ValueError with all errors joined."""
    errors = []

    # Batch size
    try:
        validate_batch_size(args.whisper_batch_size)
    except ValueError as e:
        errors.append(str(e))

    # Chunk size (int override)
    try:
        validate_chunk_size(args.whisper_chunk_size)
    except ValueError as e:
        errors.append(str(e))

    # Chunk size (string override)
    if args.chunk_size is not None:
        try:
            int_val = int(args.chunk_size)
            if int_val < 100:
                errors.append(f"Chunk size must be >= 100, got {int_val}")
        except ValueError:
            errors.append(f"Chunk size must be a valid integer, got '{args.chunk_size}'")

    # Duration range
    try:
        validate_duration_range(args.min_duration, args.max_duration)
    except ValueError as e:
        errors.append(str(e))

    # Project path
    try:
        validate_project_path(args.project_path)
    except ValueError as e:
        errors.append(str(e))

    if errors:
        raise ValueError("\n".join(errors))
