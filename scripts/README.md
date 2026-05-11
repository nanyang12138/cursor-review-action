# Scripts

Runtime entrypoints:

- `install-cursor.sh`: installs Cursor CLI when the caller has not installed it.
- `cursor_review.py`: implements command parsing, config loading, diff preparation, filtering, prompt building, Cursor invocation, findings parsing, and comment rendering.

The first version keeps the core review pipeline in one Python runner to avoid fragile shell/YAML parsing across repositories. The internal functions are intentionally split by responsibility so they can be moved into separate scripts or modules later without changing the public action interface.
