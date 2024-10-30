# main.py
import telegram
from telegram.ext import ApplicationBuilder, CommandHandler
from dotenv import load_dotenv
import os
import asyncio
from commands import total_command, tvl_command, calc_command

# .env 파일 로드
load_dotenv()

token = os.environ.get('TELEGRAM_BOT_TOKEN')
chat_id = os.environ.get('chat_id')

class TelegramBot:
    def __init__(self, name, token, chat_id):
        self.core = telegram.Bot(token)
        self.application = ApplicationBuilder().token(token).build()
        self.id = chat_id
        self.name = name

    async def send_message(self, text, parse_mode=None):
        if self.id:
            await self.core.send_message(chat_id=self.id, text=text, parse_mode=parse_mode)
        else:
            print("Chat ID not set")

    def add_handler(self, cmd, func):
        self.application.add_handler(CommandHandler(cmd, func))

    async def start(self):
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

async def main():
    kaia_bot = TelegramBot("kaia_bot", token, chat_id)
    kaia_bot.add_handler("total", total_command)
    kaia_bot.add_handler("tvl", tvl_command)
    kaia_bot.add_handler("calc", calc_command)

    await kaia_bot.start()

    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())