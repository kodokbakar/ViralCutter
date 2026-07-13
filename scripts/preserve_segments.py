import json
import os
import re
import shutil


CUT_SUFFIX = "_original_scale.mp4"


def extract_index(path):
    name = os.path.basename(path)

    match = re.match(r"^(\d+)[_-]", name)
    if match:
        return int(match.group(1))

    match = re.search(r"(?:output|segment|final-output)[-_]?(\d+)", name, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return 0


def cut_sort_key(path):
    return (extract_index(path), os.path.basename(path).lower())


def preserve_original_scale(project_folder="tmp"):
    """
    Preserve cut videos without face detection/cropping.

    Input:
        project_folder/cuts/*_original_scale.mp4

    Output:
        project_folder/final/*.mp4

    This keeps the source framing/resolution and still produces final/
    so subtitle burning and compilation continue to work.
    """
    cuts_folder = os.path.join(project_folder, "cuts")
    final_folder = os.path.join(project_folder, "final")
    os.makedirs(final_folder, exist_ok=True)

    if not os.path.isdir(cuts_folder):
        raise FileNotFoundError(f"Cuts folder not found: {cuts_folder}")

    cut_files = [
        os.path.join(cuts_folder, name)
        for name in os.listdir(cuts_folder)
        if name.endswith(CUT_SUFFIX)
    ]
    cut_files.sort(key=cut_sort_key)

    if not cut_files:
        raise FileNotFoundError(f"No cut videos found in: {cuts_folder}")

    face_modes = {}
    copied_files = []

    for source_path in cut_files:
        source_name = os.path.basename(source_path)
        base_name = source_name.replace(CUT_SUFFIX, "")
        index = extract_index(source_path)

        target_path = os.path.join(final_folder, f"{base_name}.mp4")

        if os.path.exists(target_path):
            os.remove(target_path)

        shutil.copy2(source_path, target_path)
        copied_files.append(target_path)
        face_modes[f"output{index:03d}"] = "none"

        print(f"Preserved original scale: {source_name} -> {os.path.basename(target_path)}")

    modes_file = os.path.join(project_folder, "face_modes.json")
    with open(modes_file, "w", encoding="utf-8") as f:
        json.dump(face_modes, f, indent=4)

    print(f"Face mode stats saved: {modes_file}")
    return copied_files