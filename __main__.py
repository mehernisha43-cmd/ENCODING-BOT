
import dns.resolver
from pyrogram import idle

from . import PLUGIN_CONFIG, app, log

dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = [
    '8.8.8.8']  # this is a google public dns


async def main():
    # Keep startup independent of any stale/absolute plugin setting.  The
    # loader must import VideoEncoder.plugins as a Python package.
    app.plugins = PLUGIN_CONFIG.copy()
    await app.start()
    if log is not None:
        await app.send_message(chat_id=log, text=f'<b>Bot Started! @{(await app.get_me()).username}</b>')
    await idle()
    await app.stop()

app.loop.run_until_complete(main())
