import httpx
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, ArgPlainText

# 定义命令
sunset = on_command("火烧云", aliases={"sunset"}, priority=5)
sunset_map = on_command("火烧云地图", priority=5)
stop_command = on_command("退出", priority=5)
help_command = on_command("火烧云帮助", priority=5)

API_URL = "https://sunsetbot.top/"

# 第一个处理函数：处理命令参数
@sunset.handle()
async def handle_first_receive(matcher: Matcher, args: Message = CommandArg()):
    if args.extract_plain_text():
        parts = args.extract_plain_text().split()
        if len(parts) >= 2:
            matcher.set_arg("location", Message(parts[0]))
            matcher.set_arg("event_type", Message(parts[1]))
        elif len(parts) == 1:
            matcher.set_arg("location", Message(parts[0]))

# 第二个处理函数：询问用户输入地区
@sunset.got("location", prompt="请输入地区名称")
@sunset.got("event_type", prompt="请输入查询类型（今日日出/今日日落/明日日出/明日日落）")
async def handle_location(location: str = ArgPlainText(), event_type: str = ArgPlainText()):
    # 解析 event_type
    event_map = {
        "今日日出": "rise_1",
        "今日日落": "set_1",
        "明日日出": "rise_2",
        "明日日落": "set_2"
    }
    event = event_map.get(event_type)

    if event is None:
        await sunset.reject("无效的查询类型，请输入今日日出、今日日落、明日日出或明日日落")

    # 调用 API 获取火烧云结果
    query_city = location
    query_id = "9218015"
    api_url = f"{API_URL}?query_id={query_id}&intend=select_city&query_city={query_city}&event_date=None&event={event}&times=None"

    async with httpx.AsyncClient() as client:
        response = await client.get(api_url)
        data = response.json()

    if data["status"] == "ok":
        img_href = data["img_href"]
        img_summary = data["img_summary"]
        tb_aod = data["tb_aod"]
        tb_event_time = data["tb_event_time"]
        tb_quality = data["tb_quality"]

        # 去除 HTML 标签并格式化输出
        img_summary_clean = img_summary.replace("&ensp;", "").replace("<b>", "").replace("</b>", "").replace("<br>", "\n")
        tb_aod_clean = tb_aod.replace("<br>", " ")
        tb_event_time_clean = tb_event_time.replace("<br>", " ")
        tb_quality_clean = tb_quality.replace("<br>", " ")

        message = (
            f"{img_summary_clean}\n"
            f"时间: {tb_event_time_clean}\n"
            f"质量: {tb_quality_clean}\n"
            f"AOD: {tb_aod_clean}"
        )

        # 构造实际图片链接
        img_url = f"https://sunsetbot.top/static{img_href.replace('/image', '/media')}"

        # 发送图片和消息
        await sunset.send(MessageSegment.text(message))
        await sunset.send(MessageSegment.image(img_url))
    else:
        await sunset.finish("未能获取火烧云信息，请检查地区名称是否正确。")

# 新增火烧云地图命令处理函数
@sunset_map.handle()
async def handle_map_first_receive(matcher: Matcher, args: Message = CommandArg()):
    if args.extract_plain_text():
        parts = args.extract_plain_text().split()
        if len(parts) >= 2:
            matcher.set_arg("region", Message(parts[0]))
            matcher.set_arg("event_type", Message(parts[1]))
        else:
            await sunset_map.finish("请提供地区和查询类型（今日日出/今日日落/明日日出/明日日落）")

@sunset_map.got("region", prompt="请输入查询的地区名称 (中东/东北/西南/南海/西北/日本)")
@sunset_map.got("event_type", prompt="请输入查询类型（今日日出/今日日落/明日日出/明日日落）")
async def handle_map(region: str = ArgPlainText(), event_type: str = ArgPlainText()):
    # 解析 event_type
    event_map = {
        "今日日出": "rise_1",
        "今日日落": "set_1",
        "明日日出": "rise_2",
        "明日日落": "set_2"
    }
    event = event_map.get(event_type)

    if event is None:
        await sunset_map.reject("无效的查询类型，请输入今日日出、今日日落、明日日出或明日日落")

    # 调用 API 获取火烧云地图结果
    api_url = f"{API_URL}map/?region={region}&event={event}&intend=select_region"

    async with httpx.AsyncClient() as client:
        response = await client.get(api_url)
        data = response.json()

    if data["status"] == "ok":
        map_des = data["map_des"]
        map_img_src = data["map_img_src"]

        # 构造实际图片链接
        img_url = f"https://sunsetbot.top{map_img_src}"

        # 发送图片和消息
        await sunset_map.send(MessageSegment.text(map_des))
        await sunset_map.send(MessageSegment.image(img_url))
    else:
        await sunset_map.finish("未能获取火烧云地图信息，请检查地区名称是否正确。")

# 退出命令处理函数
@stop_command.handle()
async def handle_stop():
    await stop_command.finish("操作已停止。")

# 帮助命令处理函数
@help_command.handle()
async def handle_help():
    help_text = (
        "火烧云鲜艳度（某种程度上表明火烧云质量）:\n"
        " 火烧云的鲜艳度的计算会考虑以下几个方面因素：火烧云的持续时间、火烧云的亮度与颜色、火烧云的云量（包括相态与含水量）、火烧云占据本地天空的面积、云底高度、不同层次云层之间的照明与遮挡关系，以及气溶胶光学厚度/大气浑浊度。\n"
        " - 0.001-0.05：微微烧，或者火烧云云况不典型没有预报出来；\n"
        " - 0.05~0.2：小烧，大气很通透的情况下才会比较好看；\n"
        " - 0.2~0.4：小烧到中等烧；\n"
        " - 0.4~0.6：中等烧，比较值得看的火烧云；\n"
        " - 0.6~0.8：中等烧到大烧程度的火烧云；\n"
        " - 0.8~1.0：不是很完美的大烧火烧云，例如云量没有最高、大气偏污、持续时间偏短、有低云遮挡等；\n"
        " - 1.0~1.5：典型的火烧云大烧；\n"
        " - 1.5~2.0：优质大烧，火烧云范围广、云量大（不一定满云量）、颜色明亮、持续时间长，且大气通透；\n"
        " - 2.0~2.5：世纪大烧，火烧云范围很广、接近满云量、颜色明亮鲜艳、持续时间长，且大气非常通透；\n"
        "\n"
        "AOD（气溶胶光学厚度/天空浑浊度）:\n"
        " AOD（气溶胶光学厚度/天空浑浊度）表明了气溶胶颗粒在垂直方向对光线的遮挡和散射效果。当气溶胶光学厚度较大的时候，天空中的光线在到达地面前会被气溶胶明显散射和吸收，导致天空颜色的饱和度与亮度下降，使得天空看起来污浊。\n"
        " - 0.0~0.1：（如果天气晴朗）高级水晶天，多见于青藏高原；\n"
        " - 0.1~0.2：（如果天气晴朗）普通水晶天，天空湛蓝；\n"
        " - 0.2~0.3：（如果天气晴朗）不算水晶天但也有蓝天；\n"
        " - 0.3~0.4：普通的天空；\n"
        " - 0.4~0.6：天空看起来会有点污；\n"
        " - 0.6~0.8：天空会相当的污，地面附近可能有霾；\n"
        " - >0.8：非常污的天空，地面附近可能有比较重的霾；\n"
        "\n"
        "使用说明:\n"
        " 注意图片上方写的日出和日落的日期以及预报时次。对于晚霞来说上午时次是比较新的预报，中午时次是最新的预报；而对朝霞来说傍晚时次是比较新的预报。\n"
        " 大气截面图可以提供详细的关于火烧云云况的信息，如：云况类型、气溶胶分布等，读者可以通过分析所在城市的日出/日落大气截面图判断火烧云的情况（如云况类型、云种、火烧云颜色、持续时间、伴随的其他天象等）以及可能的翻车方式。基于数值预报的火烧云预测准确率较为不令人满意，且目前此产品无法直接预报对流云火烧云，因此翻车总是可能的。\n"
    )
    help_image_url = "https://sunsetbot.top/static/media/static_image/reference_cross_section.jpg"
    
    await help_command.send(MessageSegment.text(help_text))
    await help_command.send(MessageSegment.image(help_image_url))