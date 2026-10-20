import logging
import os
import time
from io import BytesIO, StringIO
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv
from pyrogram import Client

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / "config.env")
load_dotenv(BASE_DIR / ".env")
botStartTime = time.time()


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _int(name: str, default=None, required=False) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        if required:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def _ids(name: str, default=None, required=False):
    raw = os.getenv(name, "").replace(",", " ").split()
    if not raw:
        if required:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return list(default or [])
    try:
        return sorted({int(item) for item in raw})
    except ValueError as exc:
        raise RuntimeError(f"{name} must contain integer IDs separated by spaces or commas") from exc


api_id = _int("API_ID", required=True)
api_hash = _required("API_HASH")
bot_token = _required("BOT_TOKEN")
database = _required("MONGO_URI")
session = os.getenv("DB_NAME", os.getenv("SESSION_NAME", "video_encoder"))
drive_dir = os.getenv("DRIVE_DIR", "").strip() or None
index = os.getenv("INDEX_URL", "").strip() or None
download_dir = os.path.abspath(os.getenv("DOWNLOAD_DIR", "/tmp/downloads"))
encode_dir = os.path.abspath(os.getenv("ENCODE_DIR", "/tmp/encode"))
max_concurrent_encodings = max(1, _int("MAX_CONCURRENT_ENCODINGS", 1))
owner = _ids("OWNER_ID", required=True)
sudo_users = _ids("SUDO_USERS")
everyone = _ids("EVERYONE_CHATS")
all = sorted(set(everyone + sudo_users + owner))
log = _int("LOG_CHANNEL", default=None)

for directory in (download_dir, encode_dir, BASE_DIR / "VideoEncoder/utils/extras"):
    Path(directory).mkdir(parents=True, exist_ok=True)

PROGRESS = """
• {0} of {1}
• Speed: {2}
• ETA: {3}
"""
video_mimetype = [
    "video/x-flv", "video/mp4", "application/x-mpegURL", "video/MP2T",
    "video/3gpp", "video/quicktime", "video/x-msvideo", "video/x-ms-wmv",
    "video/x-matroska", "video/webm", "video/x-m4v", "video/mpeg",
]


def memory_file(name=None, contents=None, *, bytes=True):
    if isinstance(contents, str) and bytes:
        contents = contents.encode()
    file = BytesIO() if bytes else StringIO()
    if name:
        file.name = name
    if contents:
        file.write(contents)
        file.seek(0)
    return file

LOG_PATH = BASE_DIR / "VideoEncoder/utils/extras/logs.txt"
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[RotatingFileHandler(LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"), logging.StreamHandler()],
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)
LOGGER = logging.getLogger(__name__)

data = []
app = Client(
    session,
    bot_token=bot_token,
    api_id=api_id,
    api_hash=api_hash,
    plugins={"root": str(BASE_DIR / "VideoEncoder/plugins")},
    sleep_threshold=30,
    max_concurrent_transmissions=16,
    workers=16,
    ipv6=False,
)
