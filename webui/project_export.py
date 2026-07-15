import os
import zipfile


EXPORT_FOLDERS = [
    "cuts",
    "final",
    "burned_sub",
    "compiled",
]

EXPORT_FILES = [
    "viral_segments.txt",
    "prompt.txt",
    "webui_run.log",
    "process_config.json",
]

ROOT_EXTRA_PATTERNS = [
    "compilation.mp4",
    "compilation.srt",
]


def _safe_project_name(project_path):
    name = os.path.basename(os.path.abspath(project_path)).strip()
    return name or "project"


def _add_file(zip_file, file_path, arcname):
    if not os.path.isfile(file_path):
        return 0

    zip_file.write(file_path, arcname)
    return 1


def _add_folder(zip_file, project_path, folder_name):
    folder_path = os.path.join(project_path, folder_name)

    if not os.path.isdir(folder_path):
        return 0

    added = 0

    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [
            d for d in dirs
            if d not in {"__pycache__", ".ipynb_checkpoints"}
        ]

        for filename in files:
            if filename.endswith(".zip"):
                continue

            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, project_path)
            zip_file.write(file_path, rel_path)
            added += 1

    return added


def build_project_zip(project_path):
    if not project_path:
        raise ValueError("No project selected.")

    project_path = os.path.abspath(project_path)

    if not os.path.isdir(project_path):
        raise FileNotFoundError(f"Project folder not found: {project_path}")

    project_name = _safe_project_name(project_path)
    zip_path = os.path.join(project_path, f"{project_name}_export.zip")

    if os.path.exists(zip_path):
        os.remove(zip_path)

    added = 0

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
        for folder_name in EXPORT_FOLDERS:
            added += _add_folder(zip_file, project_path, folder_name)

        for filename in EXPORT_FILES:
            added += _add_file(
                zip_file,
                os.path.join(project_path, filename),
                filename,
            )

        # Current compile_segments.py writes compilation.mp4 at project root,
        # not inside compiled/. Include it so compiled output is not missed.
        for filename in ROOT_EXTRA_PATTERNS:
            added += _add_file(
                zip_file,
                os.path.join(project_path, filename),
                filename,
            )

    if added == 0:
        os.remove(zip_path)
        raise FileNotFoundError(f"No exportable files found in: {project_path}")

    return zip_path