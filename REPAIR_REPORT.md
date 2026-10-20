# Video Encoder Bot Repair Report

## Scope

The uploaded `ENCODING-BOT-master` project was inspected and repaired in place. The existing Pyrofork/Pyrogram bot architecture, MongoDB-backed settings, Telegram upload flow, command names, and FFmpeg-based workflow were retained.

## Confirmed issues repaired

- Startup required optional variables such as `DOWNLOAD_DIR`, `ENCODE_DIR`, `EVERYONE_CHATS`, and `LOG_CHANNEL`, causing `TypeError`/`ValueError` before the bot could start. Configuration now validates required values, parses ID lists safely, supplies `/tmp/downloads` and `/tmp/encode` defaults, creates directories, and supports `MAX_CONCURRENT_ENCODINGS`.
- The bot used a hard-coded administrator ID and hard-coded default authorized/sudo IDs. These were removed; authorization now comes from the configured owner/sudo/auth lists and persisted MongoDB data.
- The FFmpeg command was assembled from shell-like strings and contained invalid/fragile option combinations. It now uses a subprocess argument list, safe input/output paths, real stream mapping, configurable codec/preset/CRF/audio/resolution settings, cancellation cleanup, nonzero-exit handling, output-size checks, and FFprobe validation.
- The previous progress implementation could divide by zero, used incorrect path concatenation, polled a shared file incorrectly, and called `communicate()` twice. The encoding path no longer reports success until FFmpeg and FFprobe both validate the output.
- Subtitle extraction now verifies supported subtitle streams and only reports success when FFmpeg actually creates a nonempty subtitle file. Unsafe wildcard `mv` commands and global font-directory modifications were removed.
- Encoding/upload cleanup now runs in `finally`, including failure paths. Temporary input, output, and per-task subtitle files are removed after processing.
- URL-provided filenames are reduced to a basename before joining with the download directory, preventing path traversal. Completed downloads are checked for existence and nonzero size.
- Archive extraction now uses an absolute executable path and checks the extractor exit code.
- The cancellation callback used a missing slash in the status path, referenced a nonexistent hard-coded process path, and trusted a hard-coded administrator ID. These were corrected.
- The `source` command was accidentally registered as the concatenated command `source` only through an obscure expression and `RPCError` was not imported. Both were corrected explicitly.
- Docker deployment now uses `python:3.10-slim-bookworm`, `libgl1`, FFmpeg, an explicit `/app` work directory, executable startup/extractor files, and the existing `python -m VideoEncoder` entry point.
- `requirements.txt` declares a compatible setuptools range for the legacy `lk21` package.

## Files changed

- `VideoEncoder/__init__.py`
- `VideoEncoder/__main__.py`
- `VideoEncoder/utils/encoding.py`
- `VideoEncoder/utils/helper.py`
- `VideoEncoder/utils/tasks.py`
- `VideoEncoder/utils/database/database.py`
- `VideoEncoder/utils/__init__.py`
- `VideoEncoder/plugins/callbacks_.py`
- `Dockerfile`
- `requirements.txt`
- `.env.example`
- `REPAIR_REPORT.md`

## Checks performed

- Python compilation: **passed** with `python3 -m compileall -q .`.
- Dependency resolution: all requirements resolved in an isolated Python 3.12 test environment after excluding `TgCrypto` for that local test; `TgCrypto` itself could not build because the sandbox Python 3.12 environment lacks `Python.h`. The target Docker image installs `python3-dev`, and the project remains configured for Python 3.10 as requested.
- Import/module loading with dummy configuration: **passed** for `VideoEncoder`, encoding utilities, helper utilities, and task utilities. The test emitted the expected warning that TgCrypto was not installed in the local test venv.
- FFmpeg and FFprobe availability: **passed** locally.
- Real local encode: **passed**. A generated test video with video and audio was encoded through the repaired pipeline to H.264/AAC MP4, producing a 145,977-byte file that FFprobe read successfully.
- Live Telegram API, Telegram download/upload, MongoDB connectivity, Google Drive upload, and Railway deployment: **not performed**, because no credentials or live service access were provided.
- Docker image build was not performed because Docker is not available in the sandbox; the Dockerfile was statically reviewed and its package list no longer contains the Bullseye-only `libgl1-mesa-glx` package.

## Known limitations

- Telegram and MongoDB behavior still requires live credentials and service connectivity to verify end-to-end.
- Railway's filesystem is ephemeral. `/tmp/downloads` and `/tmp/encode` are temporary working storage, not permanent user storage.
- `TgCrypto` is strongly recommended for Telegram transfer performance. The local sandbox could not build it because its Python headers were unavailable; the target Docker build includes development headers.
- Existing optional Google Drive/direct-link integrations remain dependent on their external credentials and upstream services.

## Railway deployment steps

1. Download the repaired ZIP and extract it locally.
2. Update the existing GitHub repository by replacing the project files from the extracted folder. Do not delete `.github`, `VideoEncoder`, `Dockerfile`, `requirements.txt`, `Procfile`, `run.sh`, or `extract`.
3. In Railway, open the service's **Variables** section and set the variables documented in `.env.example`: `API_ID`, `API_HASH`, `BOT_TOKEN`, `MONGO_URI`, and `OWNER_ID` are required. Set `DB_NAME`; optionally set `SUDO_USERS`, `EVERYONE_CHATS`, `LOG_CHANNEL`, `DOWNLOAD_DIR`, `ENCODE_DIR`, `MAX_CONCURRENT_ENCODINGS`, and `LOG_LEVEL`.
4. Do not commit a real `.env` or `config.env`. Use Railway Variables for secrets.
5. Trigger a new deployment from the updated GitHub commit. Railway will build the supplied Dockerfile.
6. Check build logs for successful `apt-get` and Python dependency installation. Check runtime logs for the Pyrogram startup message; a configured `LOG_CHANNEL` receives the startup notification.
7. In Telegram, send `/start`, then reply to a small video with `/dl`. Confirm the bot downloads, performs a real FFmpeg encode, validates the output, uploads it, and removes temporary files.
8. If a job fails, inspect Railway runtime logs for the FFmpeg stderr tail and verify that the MongoDB URI is reachable from Railway.
