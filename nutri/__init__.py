from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message
from nonebot.params import CommandArg
from nonebot.exception import FinishedException  # 新增导入
from bs4 import BeautifulSoup
import aiohttp

nutrimatics = on_command("nutrimatics", aliases={"nutri", "牛吹"}, priority=5)
a1z26 = on_command("A1Z26", aliases={"a1z26"}, priority=5)

@nutrimatics.handle()
async def handle_nutrimatics(args: Message = CommandArg()):
    query = args.extract_plain_text().strip()
    if not query:
        await nutrimatics.finish("请输入要查询的内容～")
        return  # 明确返回避免后续执行
    
    url = f"https://nutrimatic.org/2024/?q={query}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html = await response.text()
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # 错误检测
                if error_tag := soup.find('font', color='red'):
                    await nutrimatics.finish(f"查询错误：{error_tag.text.strip()}")
                    return
                
                # 结果提取
                results = [
                    span.get_text(strip=True)
                    for span in soup.find_all('span', style=lambda x: 'font-size' in x)
                ][:20]
                
                if not results:
                    await nutrimatics.finish("未找到匹配结果")
                    return
                    
                reply = "前20个匹配结果：\n" + "\n".join(
                    f"{i+1}. {res}" for i, res in enumerate(results)
                )
                await nutrimatics.finish(reply)

    except FinishedException:  # 特殊处理完成异常
        raise  # 直接重新抛出
    except Exception as e:  # 其他异常正常处理
        await nutrimatics.finish(f"请求失败：{str(e)}")

@a1z26.handle()
async def handle_a1z26(args: Message = CommandArg()):
    input_str = args.extract_plain_text().strip()
    if not input_str:
        await a1z26.finish("请输入数字序列～")
        return

    parts = input_str.split()
    numbers = []
    
    try:
        for part in parts:
            # 检查是否为纯数字
            if not part.isdigit():
                await a1z26.finish(f"错误：'{part}' 不是有效数字")
                return
            
            num = int(part)
            # 检查数字范围
            if not (1 <= num <= 26):
                await a1z26.finish(f"错误：数字 {num} 超出 1-26 范围")
                return
            
            numbers.append(num)
        
        # 转换为字母（小写）
        result = ''.join([chr(96 + num) for num in numbers])
        await a1z26.finish(f"转换结果：{result}")

    except FinishedException:
        raise
    except Exception as e:
        await a1z26.finish(f"处理异常：{str(e)}")