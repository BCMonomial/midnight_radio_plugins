from typing import Dict, Tuple, Optional, Set, List
from nonebot import on_command, get_driver
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import (
    MessageSegment,
    Event,
    Message,
    GROUP_ADMIN,
    GROUP_OWNER,
)
from nonebot.permission import SUPERUSER
from nonebot_plugin_htmlrender import get_new_page #  确保已安装: pip install nonebot-plugin-htmlrender

# 游戏状态存储结构
games: Dict[int, dict] = {}

# ---------- 工具函数 ----------
def init_game(group_id: int):
    """初始化游戏"""
    games[group_id] = {
        "board": [[{"occupied": None, "color": None} for _ in range(10)] for _ in range(10)],
        "players": [],  # [player1_id, player2_id]
        "current_player_idx": 0,  # 0 for players[0], 1 for players[1]
        "started": False,
        "game_over": False,
        "turn_count": 0,
    }

def coord_to_index(coord: str) -> Optional[Tuple[int, int]]:
    """坐标转换（带严格校验）"""
    if not coord or len(coord) < 2:
        return None
    try:
        col_str = coord[0].upper()
        row_str = coord[1:]
        if not (col_str.isalpha() and row_str.isdigit()):
            return None
        
        col = ord(col_str) - ord("A")
        row = int(row_str) - 1
        if 0 <= col < 10 and 0 <= row < 10:
            return (row, col)
        return None
    except:
        return None

def check_three_in_line(board: List[List[Dict]], player_id: str, last_move: Tuple[int, int]) -> Set[Tuple[int, int]]:
    """
    检测落子后形成的所有三连，并返回对应的九宫格染色区域。
    修正逻辑：以形成三连的中间棋子为中心进行九宫格染色。
    一次落子可能形成多个方向上的三连。

    参数：
        board: 棋盘二维数组
        player_id: 当前玩家ID (实际是 user_id)
        last_move: 最新落子坐标 (row, col)

    返回：
        需要染色的格子坐标集合 (九宫格中心集合)
    """
    r, c = last_move
    affected_nine_grids_centers = set() # 存储三连的中心棋子坐标

    # 定义8个方向 (dr, dc)
    # (水平, 垂直, 主对角线, 副对角线)及其反方向
    directions = [
        (0, 1), (1, 0), (1, 1), (1, -1),
        (0, -1), (-1, 0), (-1, -1), (-1, 1)
    ]

    # 为了避免重复检查同一条线，我们只检查从新落子点开始的特定组合
    # 考虑新落子点 P 作为三连的:
    # 1. P X X (P是起点)
    # 2. X P X (P是中点)
    # 3. X X P (P是终点)

    for dr, dc in directions[:4]: # 只需检查4个基础方向，另4个会被覆盖
        # 检查三种模式
        # 模式 1: (P) O O (P是当前子，O是同色子)
        # 中点是 P + 1*dir
        p1 = (r, c)
        p2 = (r + dr, c + dc)
        p3 = (r + 2 * dr, c + 2 * dc)
        if (0 <= p2[0] < 10 and 0 <= p2[1] < 10 and
            0 <= p3[0] < 10 and 0 <= p3[1] < 10 and
            board[p1[0]][p1[1]]["occupied"] == player_id and
            board[p2[0]][p2[1]]["occupied"] == player_id and
            board[p3[0]][p3[1]]["occupied"] == player_id):
            affected_nine_grids_centers.add(p2) # 中心是p2

        # 模式 2: O (P) O
        # 中点是 P
        p1 = (r - dr, c - dc)
        p2 = (r, c) # 当前落子
        p3 = (r + dr, c + dc)
        if (0 <= p1[0] < 10 and 0 <= p1[1] < 10 and
            0 <= p3[0] < 10 and 0 <= p3[1] < 10 and
            board[p1[0]][p1[1]]["occupied"] == player_id and
            board[p2[0]][p2[1]]["occupied"] == player_id and # 确保当前落子点是正确的（理论上总是）
            board[p3[0]][p3[1]]["occupied"] == player_id):
            affected_nine_grids_centers.add(p2) # 中心是p2 (即last_move)

        # 模式 3: O O (P)
        # 中点是 P - 1*dir
        p1 = (r - 2 * dr, c - 2 * dc)
        p2 = (r - dr, c - dc)
        p3 = (r, c) # 当前落子
        if (0 <= p1[0] < 10 and 0 <= p1[1] < 10 and
            0 <= p2[0] < 10 and 0 <= p2[1] < 10 and
            board[p1[0]][p1[1]]["occupied"] == player_id and
            board[p2[0]][p2[1]]["occupied"] == player_id and
            board[p3[0]][p3[1]]["occupied"] == player_id): # 确保当前落子点是正确的
            affected_nine_grids_centers.add(p2) # 中心是p2

    # 根据中心点集合，生成所有需要染色的九宫格区域
    cells_to_color = set()
    for center_r, center_c in affected_nine_grids_centers:
        for dr_nine in [-1, 0, 1]:
            for dc_nine in [-1, 0, 1]:
                nr, nc = center_r + dr_nine, center_c + dc_nine
                if 0 <= nr < 10 and 0 <= nc < 10:
                    cells_to_color.add((nr, nc))
    
    return cells_to_color


def apply_color(board: List[List[Dict]], player_id: str, positions: Set[Tuple[int, int]]):
    """应用颜色"""
    for r, c in positions:
        board[r][c]["color"] = player_id # player_id is user_id

async def generate_board_image(group_id: int) -> Optional[bytes]:
    """生成优化后的棋盘图片"""
    if group_id not in games:
        return None
    game = games[group_id]
    board_data = game["board"]
    players = game["players"] # [player1_id, player2_id]
    
    # 确保有两个玩家，否则颜色定义会出问题
    player1_id = players[0] if len(players) > 0 else "P1_Unknown"
    player2_id = players[1] if len(players) > 1 else "P2_Unknown"

    # 计算染色区域得分
    scores = {player1_id: 0, player2_id: 0}
    for r in range(10):
        for c in range(10):
            cell_color = board_data[r][c]["color"]
            if cell_color == player1_id:
                scores[player1_id] += 1
            elif cell_color == player2_id:
                scores[player2_id] += 1
    
    total_occupied_cells = sum(1 for row in board_data for cell in row if cell["occupied"])


    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-T">
        <title>合群之落棋盘</title>
        <style>
            :root {{
                --board-bg: #f0e6d2; /* 棋盘背景色，暖黄色 */
                --cell-border: #b8a07e; /* 棋盘线颜色 */
                --coord-text: #5c4d3c; /* 坐标文字颜色 */
                --stone-size-ratio: 0.75; /* 棋子相对于格子大小的比例 */
                --player1-color-id: '{player1_id}'; /* 存储玩家ID，以便JS或CSS选择器使用 */
                --player2-color-id: '{player2_id}';
                
                /* 玩家1 (黑棋) 染色区域 */
                --player1-area-bg-start: #ffcdd2; /* 浅红 */
                --player1-area-bg-end: #ef9a9a;   /* 稍深红 */
                
                /* 玩家2 (白棋) 染色区域 */
                --player2-area-bg-start: #bbdefb; /* 浅蓝 */
                --player2-area-bg-end: #90caf9;   /* 稍深蓝 */

                --black-stone-main: #212121;
                --black-stone-highlight: #424242;
                --white-stone-main: #e0e0e0;
                --white-stone-highlight: #ffffff;
                --white-stone-border: #bdbdbd;
            }}
            body {{
                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                background-color: #f7f7f7;
                padding: 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            .game-container {{
                background-color: #fff;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 8px 16px rgba(0,0,0,0.1);
            }}
            .board-wrapper {{
                display: grid;
                grid-template-columns: 30px 1fr; /* 列坐标 + 棋盘 */
                grid-template-rows: 30px 1fr;    /*行坐标 + 棋盘 */
                width: 530px; /* 500px for board + 30px for coords */
                height: 530px;
                margin-bottom: 20px;
            }}
            .coord-label {{
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                color: var(--coord-text);
                font-weight: bold;
            }}
            .board {{
                display: grid;
                grid-template-columns: repeat(10, 1fr);
                grid-template-rows: repeat(10, 1fr);
                width: 500px;
                height: 500px;
                border: 2px solid var(--cell-border);
                background-color: var(--board-bg);
            }}
            .cell {{
                border: 1px solid var(--cell-border);
                position: relative;
                display: flex;
                align-items: center;
                justify-content: center;
                background-size: cover; /* For gradient backgrounds */
            }}
            /* Cell coloring based on player ID */
            .cell.colored.player1 {{
                background: linear-gradient(135deg, var(--player1-area-bg-start), var(--player1-area-bg-end));
            }}
            .cell.colored.player2 {{
                background: linear-gradient(135deg, var(--player2-area-bg-start), var(--player2-area-bg-end));
            }}

            .stone {{
                width: calc(100% * var(--stone-size-ratio));
                height: calc(100% * var(--stone-size-ratio));
                border-radius: 50%;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3), inset 0 1px 2px rgba(255,255,255,0.2);
                position: absolute; /* Keep absolute for fine-tuning if needed */
                left: 50%;
                top: 50%;
                transform: translate(-50%, -50%);
            }}
            .stone.black {{
                background: radial-gradient(circle at 30% 30%, var(--black-stone-highlight), var(--black-stone-main));
            }}
            .stone.white {{
                background: radial-gradient(circle at 70% 70%, var(--white-stone-highlight), var(--white-stone-main));
                border: 1px solid var(--white-stone-border);
            }}
            .info-panel {{
                text-align: center;
                background-color: #e9e9e9;
                padding: 15px;
                border-radius: 8px;
            }}
            .info-panel p {{ margin: 5px 0; font-size: 16px; }}
            .info-panel .score {{ font-weight: bold; }}
            .player1-text {{ color: #c62828; }} /* Darker red for text */
            .player2-text {{ color: #1565c0; }} /* Darker blue for text */
        </style>
    </head>
    <body>
        <div class="game-container">
            <div class="board-wrapper">
                <div></div> <!-- Top-left empty cell -->
                <div style="display: grid; grid-template-columns: repeat(10, 1fr);">
                    {''.join(f'<div class="coord-label">{chr(65 + i)}</div>' for i in range(10))}
                </div>
                <div style="display: grid; grid-template-rows: repeat(10, 1fr);">
                    {''.join(f'<div class="coord-label">{i + 1}</div>' for i in range(10))}
                </div>
                <div class="board">
    """

    for r in range(10):
        for c in range(10):
            cell_data = board_data[r][c]
            cell_classes = ["cell"]
            stone_html = ""

            if cell_data["color"] == player1_id:
                cell_classes.append("colored player1")
            elif cell_data["color"] == player2_id:
                cell_classes.append("colored player2")
            
            if cell_data["occupied"] == player1_id: # Player 1 is Black
                stone_html = '<div class="stone black"></div>'
            elif cell_data["occupied"] == player2_id: # Player 2 is White
                stone_html = '<div class="stone white"></div>'
            
            html_content += f'<div class="{" ".join(cell_classes)}">{stone_html}</div>'

    html_content += f"""
                </div>
            </div>
            <div class="info-panel">
                <p>总手数：{game['turn_count']}</p>
                <p>下一手：玩家 {game['players'][game['current_player_idx']]} ({'黑棋 ●' if game['current_player_idx'] == 0 else '白棋 ○'})</p>
                <p><span class="player1-text">玩家 {player1_id} (黑) 染色区域: <span class="score">{scores[player1_id]}</span></span></p>
                <p><span class="player2-text">玩家 {player2_id} (白) 染色区域: <span class="score">{scores[player2_id]}</span></span></p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # print(html_content) # For debugging HTML
    
    try:
        async with get_new_page(viewport={"width": 600, "height": 750}) as page:
            await page.set_content(html_content)
            img_bytes = await page.screenshot(type="png", full_page=False) # Capture only viewport
            return img_bytes
    except Exception as e:
        print(f"Error generating image with htmlrender: {e}")
        return None


async def end_game(group_id: int, ended_by_user_id: Optional[str] = None):
    """结束游戏并结算"""
    if group_id not in games: return
    game = games[group_id]
    game["game_over"] = True

    player1_id = game["players"][0] if len(game["players"]) > 0 else "P1"
    player2_id = game["players"][1] if len(game["players"]) > 1 else "P2"

    scores = {player1_id: 0, player2_id: 0}
    for r in range(10):
        for c in range(10):
            cell_color = game["board"][r][c]["color"]
            if cell_color == player1_id:
                scores[player1_id] += 1
            elif cell_color == player2_id:
                scores[player2_id] += 1
    
    p1_score = scores[player1_id]
    p2_score = scores[player2_id]

    result_msg = ""
    if p1_score == p2_score:
        result_msg = f"平局！双方染色面积均为 {p1_score}。"
    elif p1_score > p2_score:
        result_msg = f"玩家 {player1_id} (黑棋) 获胜！\n染色面积：黑 {p1_score} vs 白 {p2_score}"
    else:
        result_msg = f"玩家 {player2_id} (白棋) 获胜！\n染色面积：白 {p2_score} vs 黑 {p1_score}"

    if ended_by_user_id:
        result_msg = f"玩家 {ended_by_user_id} 提前结束了棋局。\n{result_msg}"
    else:
         result_msg = f"棋盘已满，游戏结束！\n{result_msg}"


    img_bytes = await generate_board_image(group_id) # Generate final board image
    msg_to_send = Message()
    if img_bytes:
        msg_to_send.append(MessageSegment.image(img_bytes))
    msg_to_send.append(f"\n{result_msg}")
    
    await place_cmd.send(message=msg_to_send) # Use any command that is available and has bot context
    
    if group_id in games:
        del games[group_id]

async def send_turn_message(group_id: int):
    """发送回合提示"""
    if group_id not in games or games[group_id]["game_over"]:
        return
    
    game = games[group_id]
    img_bytes = await generate_board_image(group_id)
    
    if img_bytes:
        next_player_id = game["players"][game["current_player_idx"]]
        player_role = '黑棋 ●' if game['current_player_idx'] == 0 else '白棋 ○'
        
        msg = MessageSegment.image(img_bytes) + \
              f"\n当前第 {game['turn_count']} 手。轮到玩家 {next_player_id} ({player_role}) 落子。"
        await place_cmd.send(msg) # Use any command that is available
    else:
        await place_cmd.send("棋盘生成失败，请继续游戏。")

# ---------- 命令处理器 ----------
chess = on_command("合群之落", aliases={"开始下棋", "新对局"}, priority=5, block=True)
join_cmd = on_command("加入游戏", aliases={"加入合群"}, priority=5, block=True) # Renamed for clarity
place_cmd = on_command("落子", aliases={"下", "playchess"}, priority=5, block=True) # Renamed for clarity
end_game_cmd = on_command("结束棋局", aliases={"认输"}, priority=5, block=True)
force_stop_cmd = on_command("关闭游戏", permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER, priority=5, block=True)

@chess.handle()
async def handle_chess(event: Event):
    group_id = getattr(event, "group_id", None)
    if group_id is None:
        await chess.finish("请在群聊中使用此命令。")

    if group_id in games and not games[group_id]["game_over"]:
        await chess.finish("本群已有进行中的对局。若要强制结束，请使用【关闭游戏】。")
    
    init_game(group_id)
    user_id = event.get_user_id()
    games[group_id]["players"].append(user_id) # 创建者自动成为玩家1 (黑棋)
    
    await chess.finish(
        f"新对局已创建！玩家 {user_id} 自动执黑棋 ● (染色区：红)。\n"
        "请另一位玩家使用【加入游戏】命令参与 (执白棋 ○, 染色区：蓝)。"
    )

@join_cmd.handle()
async def handle_join(event: Event):
    group_id = getattr(event, "group_id", None)
    if group_id is None:
        await join_cmd.finish("请在群聊中使用此命令。")
    user_id = event.get_user_id()

    if group_id not in games or games[group_id]["game_over"]:
        await join_cmd.finish("当前没有可加入的对局，请先使用【合群之落】创建。")
    
    game = games[group_id]
    
    if game["started"]:
        await join_cmd.finish("对局已经开始，无法加入。")
    
    if len(game["players"]) >= 2:
        await join_cmd.finish("对局人数已满（2人）。")
    
    if user_id in game["players"]:
        await join_cmd.finish("您已经在对局中。")
    
    game["players"].append(user_id)
    await join_cmd.send(f"玩家 {user_id} 加入成功，执白棋 ○ (染色区：蓝)。\n当前人数：{len(game['players'])}/2。")
    
    if len(game["players"]) == 2:
        game["started"] = True
        game["current_player_idx"] = 0 # 黑棋先手
        game["turn_count"] = 1
        await join_cmd.send("人数已满，游戏开始！")
        await send_turn_message(group_id)

@place_cmd.handle()
async def handle_place(event: Event, arg: Message = CommandArg()):
    group_id = getattr(event, "group_id", None)
    if group_id is None:
        await place_cmd.finish("请在群聊中使用此命令。")
    user_id = event.get_user_id()
    
    coord_str = arg.extract_plain_text().strip()
    if not coord_str:
        await place_cmd.finish("请指定落子坐标，例如：落子 A1")

    if group_id not in games:
        await place_cmd.finish("当前没有进行中的对局。")
    game = games[group_id]
    
    if not game["started"]:
        await place_cmd.finish("对局尚未开始或人数未满。")
    if game["game_over"]:
        await place_cmd.finish("对局已结束。")
    if user_id not in game["players"]:
        await place_cmd.finish("您不是当前对局的玩家。")
    if user_id != game["players"][game["current_player_idx"]]:
        await place_cmd.finish("现在不是您的回合。")

    pos = coord_to_index(coord_str)
    if not pos:
        await place_cmd.finish("坐标格式错误，请使用字母+数字的格式（如A1, J10）。")
    row, col = pos
    
    if game["board"][row][col]["occupied"]:
        await place_cmd.finish(f"位置 {coord_str.upper()} 已有棋子，请选择其他位置。")

    # 执行落子
    current_player_id = game["players"][game["current_player_idx"]]
    game["board"][row][col]["occupied"] = current_player_id
    
    # 检测三连并染色
    # player_id for coloring is the user_id of the current player
    affected_cells = check_three_in_line(game["board"], current_player_id, (row, col))
    if affected_cells:
        apply_color(game["board"], current_player_id, affected_cells)
        await place_cmd.send(f"玩家 {current_player_id} 形成三连，在 {len(affected_cells)} 个格子染色！")

    # 检查棋盘是否已满
    occupied_count = sum(1 for r_ in game["board"] for cell in r_ if cell["occupied"])
    if occupied_count == 100: # 10x10 board
        await end_game(group_id)
        return
    
    # 切换玩家
    game["current_player_idx"] = 1 - game["current_player_idx"]
    if game["current_player_idx"] == 0 : # New turn starts when black (player 0) is to play
        game["turn_count"] +=1

    await send_turn_message(group_id)


@end_game_cmd.handle()
async def handle_end_game_cmd(event: Event): # Renamed to avoid conflict
    group_id = getattr(event, "group_id", None)
    if group_id is None:
        await end_game_cmd.finish("请在群聊中使用此命令。")
    user_id = event.get_user_id()

    if group_id not in games:
        await end_game_cmd.finish("当前没有进行中的对局。")
    game = games[group_id]
    
    if user_id not in game["players"]:
        await end_game_cmd.finish("您不是当前对局的玩家，无法结束游戏。")
    
    # Call the main end_game logic
    await end_game(group_id, ended_by_user_id=user_id)
    # end_game now sends the message, so no need to send here unless for specific "认输" text
    # await end_game_cmd.send(f"玩家 {user_id} 已选择结束/认输。") # end_game handles this now.

@force_stop_cmd.handle()
async def handle_force_stop(event: Event):
    group_id = getattr(event, "group_id", None)
    if group_id is None:
        await force_stop_cmd.finish("请在群聊中使用此命令。")
        
    if group_id in games:
        del games[group_id]
        await force_stop_cmd.send("管理员已强制终止当前对局。")
    else:
        await force_stop_cmd.finish("当前没有进行中的对局。")