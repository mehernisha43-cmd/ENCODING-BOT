

## Railway plugin-loader crash repair

The Railway crash was caused by `plugins={"root": str(BASE_DIR / "VideoEncoder/plugins")}`. In the Docker container this evaluated to `/app/VideoEncoder/plugins`. Pyrogram's loader converts the configured root by replacing path separators with dots, so it attempted to import the invalid relative module `.app.VideoEncoder.plugins.queue`. The correct value is the Python package path `VideoEncoder.plugins`, which Pyrogram resolves to the package directory while importing handlers as `VideoEncoder.plugins.queue`, `VideoEncoder.plugins.start`, and so on.

The fix changed the client configuration in `VideoEncoder/__init__.py` to `plugins={"root": "VideoEncoder.plugins"}` and added `VideoEncoder/plugins/__init__.py` as an explicit package marker. The Docker working directory remains `/app`, and the startup command remains `python -m VideoEncoder`, so the package is available on `sys.path` in Railway.

A direct `app.load_plugins()` test passed with dummy environment values and loaded the configured plugin tree without the reported relative-import exception. Live `app.start()` was not performed because it requires valid Telegram credentials and network access to Telegram. The Dockerfile was not built locally because Docker is unavailable in the sandbox; its `WORKDIR /app` and `CMD ["python", "-m", "VideoEncoder"]` are consistent with the fixed package path.
