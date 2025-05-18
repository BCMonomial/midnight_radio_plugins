import random
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.plugin import on_command

echo = on_command("echo", rule=to_me(), priority=1, block=True)


@echo.handle()
async def echo_escape(message: Message = CommandArg()):
    message_text = message.extract_plain_text()
    img_urls = ['https://s21.ax1x.com/2024/08/07/pkxWIaQ.jpg',
    'https://s21.ax1x.com/2024/08/07/pkxWWKf.jpg',
    'https://s21.ax1x.com/2024/08/07/pkxW2xP.jpg',
    'https://s21.ax1x.com/2024/08/07/pkxWfr8.jpg',
    'https://s21.ax1x.com/2024/08/07/pkxWhqS.jpg',
    'https://s21.ax1x.com/2024/08/07/pkxW5Vg.jpg'
    ]
    if message_text.find('yasu /echo') > -1:
        await echo.finish(MessageSegment.image(random.choice(img_urls)))
    await echo.send(message=message)
