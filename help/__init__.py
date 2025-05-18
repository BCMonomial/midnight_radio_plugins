from nonebot import on_command, on_keyword, on_startswith
from nonebot.matcher import matchers


help = on_command("信息", aliases={"info"},priority=5)
wrong_slash = on_startswith("/mist", priority = 5, block = True)

@help.handle()
async def test():
    message = "Midnight_Radio deployed by BCMonomial, based on NoneBot & NapCat. \nSponsored by Hay (not the bot). \nPersonal use only. "
    await help.finish(message)

@wrong_slash.handle()
async def test2():
    message = "杠后面不要杠前面.jpg\n请使用“mist”作为 bot 称呼，而不是命令名称。"
    await help.finish(message)