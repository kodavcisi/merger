import os
import logging
from config import Config
import time
from helper_func.dbhelper import Database as Db
db = Db().setup()
from pyrogram.raw.all import layer
import pyrogram
from pyrogram import Client, __version__

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('log.txt'), logging.StreamHandler()],
    level=logging.INFO,
)
LOGGER = logging.getLogger(__name__)
botStartTime = time.time()

plugins = dict(root='plugins')

if not os.path.isdir(Config.DOWNLOAD_DIR):
    os.mkdir(Config.DOWNLOAD_DIR)
if not os.path.isdir(Config.ENCODE_DIR):
    os.mkdir(Config.ENCODE_DIR)


class Bot(Client):

    def __init__(self):
        super().__init__(
            name='mergerbot',
            api_id=Config.APP_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=343,
            plugins=plugins,
            sleep_threshold=5,
        )

    async def start(self):
        # Ensure download dir exists
        if not os.path.isdir(Config.DOWNLOAD_DIR):
            os.makedirs(Config.DOWNLOAD_DIR)

        await super().start()

        # Get owner and me info
        try:
            owner = await self.get_chat(Config.OWNER_ID)
            print(owner)
        except Exception as e:
            LOGGER.warning(f"Could not get owner chat: {e}")

        me = await self.get_me()
        self.username = '@' + me.username if me and me.username else None
        LOGGER.info(
            f"{me.first_name} with for Pyrogram v{__version__} (Layer {layer}) started on {me.username}. Premium {me.is_premium}."
        )

        # Notify owner that bot started
        if Config.OWNER_ID != 0:
            try:
                await self.send_message(text="Karanlığın küllerinden yeniden doğdum.", chat_id=Config.OWNER_ID)
            except Exception as t:
                LOGGER.error(str(t))

        # Determine log channel: try common config names, fallback to owner id
        log_chat = getattr(Config, "LOG_CHANNEL_ID", None) or getattr(Config, "LOG_CHANNEL", None) or Config.OWNER_ID

        # Check session activity and send the required message to log channel
        try:
            session_active = await self._check_session_active()
            if session_active:
                await self.send_message(chat_id=log_chat, text="4GB aktif")
            else:
                await self.send_message(chat_id=log_chat, text="4GB aktif değil")
        except Exception as e:
            LOGGER.warning(f"Failed to send session status message: {e}")

    async def _check_session_active(self) -> bool:
        """
        Tries a light API call to confirm the session is active.
        Returns True if the call succeeds, False otherwise.
        """
        try:
            # get_me is lightweight and will fail if session isn't valid/connected
            me = await self.get_me()
            # If we got a valid user, session is active
            return me is not None
        except Exception as e:
            LOGGER.debug(f"_check_session_active failed: {e}")
            return False

    async def stop(self, *args):
        if Config.OWNER_ID != 0:
            texto = f"Son nefesimi verdim.\nÖldüğümde yaşım: {time.time() - botStartTime}"
            try:
                await self.send_document(document='log.txt', caption=texto, chat_id=Config.OWNER_ID)
            except Exception as t:
                LOGGER.warning(str(t))
        await super().stop()
        LOGGER.info(msg="App Stopped.")
        exit()


app = Bot()
app.run()
