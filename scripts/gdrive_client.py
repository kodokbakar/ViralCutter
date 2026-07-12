import io
import os
import re

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, "credentials.json")
TOKEN_PATH = os.path.join(PROJECT_ROOT, "token_drive.json")


def sanitize_filename(name):
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name or "Google_Drive_Video")
    cleaned = cleaned.strip().replace(" ", "_")
    return cleaned[:80] or "Google_Drive_Video"


def format_size(size):
    if not size:
        return "unknown size"

    size = int(size)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
        size /= 1024

    return f"{size:.1f} TB"

def is_colab_runtime():
    try:
        import google.colab  # noqa: F401
        return True
    except ImportError:
        return False


def get_colab_credentials():
    from google.colab import auth
    import google.auth
    from google.auth.transport.requests import Request

    auth.authenticate_user()
    creds, _ = google.auth.default(scopes=SCOPES)

    if creds and not creds.valid:
        creds.refresh(Request())

    return creds

def get_application_default_credentials():
    import google.auth
    from google.auth.transport.requests import Request

    creds, _ = google.auth.default(scopes=SCOPES)

    if creds and not creds.valid:
        creds.refresh(Request())

    return creds

def get_credentials():
    try:
        return get_application_default_credentials()
    except Exception:
        pass

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        if not os.path.exists(CREDENTIALS_PATH):
            raise FileNotFoundError(
                "Google Drive credentials.json not found. "
                "In Colab, run auth.authenticate_user() before starting the WebUI. "
                "For local desktop use, create an OAuth Desktop Client and save it as credentials.json in the repo root."
            )

        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        creds = flow.run_local_server(port=0)

    with open(TOKEN_PATH, "w", encoding="utf-8") as token:
        token.write(creds.to_json())

    return creds

def get_drive_service():
    return build("drive", "v3", credentials=get_credentials())


def escape_drive_query(value):
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def list_drive_videos(search_query="", page_size=50):
    service = get_drive_service()

    query_parts = [
        "trashed = false",
        "mimeType contains 'video/'",
    ]

    if search_query and str(search_query).strip():
        query_parts.append(f"name contains '{escape_drive_query(search_query.strip())}'")

    response = service.files().list(
        q=" and ".join(query_parts),
        pageSize=page_size,
        fields="files(id,name,mimeType,size,modifiedTime)",
        orderBy="modifiedTime desc",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()

    return response.get("files", [])


def file_choices(files):
    choices = []
    for file in files:
        size = format_size(file.get("size"))
        modified = file.get("modifiedTime", "")[:10]
        label = f"{file.get('name', 'Untitled')} — {size} — {modified}"
        choices.append((label, file["id"]))
    return choices


def get_file_metadata(file_id):
    service = get_drive_service()
    return service.files().get(
        fileId=file_id,
        fields="id,name,mimeType,size",
        supportsAllDrives=True,
    ).execute()


def download_drive_video(file_id, file_name=None, base_root="VIRALS"):
    metadata = get_file_metadata(file_id)
    mime_type = metadata.get("mimeType", "")

    if not mime_type.startswith("video/"):
        raise ValueError(f"Selected Google Drive file is not a video: {mime_type}")

    safe_name = sanitize_filename(file_name or metadata.get("name"))
    project_folder = os.path.join(base_root, f"{safe_name}_{file_id[:8]}")
    os.makedirs(project_folder, exist_ok=True)

    output_path = os.path.join(project_folder, "input.mp4")

    if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
        print(f"Video already exists at: {output_path}")
        print("Skipping download and reusing local file.")
        return output_path, project_folder

    service = get_drive_service()
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)

    print(f"Downloading from Google Drive: {metadata.get('name')}")
    print(f"File ID: {file_id}")

    with io.FileIO(output_path, "wb") as output_file:
        downloader = MediaIoBaseDownload(output_file, request)
        done = False

        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"[gdrive] {int(status.progress() * 100)}%", flush=True)

    if not os.path.exists(output_path) or os.path.getsize(output_path) <= 1024:
        raise RuntimeError("Downloaded Google Drive file is empty or missing.")

    print(f"Download complete: {output_path}")
    return output_path, project_folder