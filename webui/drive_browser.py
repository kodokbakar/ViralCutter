import os


DRIVE_ROOT = "/content/drive/MyDrive"
VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")


def is_colab_drive_available():
    return os.path.isdir(DRIVE_ROOT)


def list_drive_videos(search_query="", limit=200):
    if not is_colab_drive_available():
        raise FileNotFoundError(
            "Google Drive is not mounted. In Colab, run drive.mount('/content/drive') before starting WebUI."
        )

    query = (search_query or "").strip().lower()
    videos = []

    for root, dirs, files in os.walk(DRIVE_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for filename in files:
            if not filename.lower().endswith(VIDEO_EXTENSIONS):
                continue

            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, DRIVE_ROOT)

            if query and query not in filename.lower() and query not in rel_path.lower():
                continue

            try:
                size_mb = os.path.getsize(full_path) / (1024 * 1024)
            except OSError:
                size_mb = 0

            label = f"{rel_path} — {size_mb:.1f} MB"
            videos.append((label, full_path))

            if len(videos) >= limit:
                return videos

    return videos