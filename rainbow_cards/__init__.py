import json
import random
from pathlib import Path
# Removed: from typing import Dict, Any, Optional, Tuple

from nonebot import on_command
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Bot, Event # Keep necessary imports
from nonebot.rule import to_me # Import the rule for at_me

# --- Try to import htmlrender ---
try:
    from nonebot_plugin_htmlrender import html_to_pic
except ImportError:
    logger.warning("Dependency 'nonebot-plugin-htmlrender' not found. Image generation will fail.")
    logger.warning("Please install it: pip install nonebot-plugin-htmlrender")
    logger.warning("Or: nb plugin install nonebot-plugin-htmlrender")
    logger.warning("And make sure playwright is installed: playwright install chromium")
    html_to_pic = None # Set to None if import fails

# --- Plugin Metadata (Optional) ---
__plugin_name__ = "彩虹卡 Rainbow Card"
__plugin_usage__ = """
抽一张彩虹卡吧！

命令:
  /彩虹卡        -> 随机抽取一张彩虹卡
  /彩虹卡 [颜色] -> 抽取指定颜色的彩虹卡 (如: /彩虹卡 蓝色)

可用颜色: 红色, 橙色, 黄色, 绿色, 蓝色, 靛色, 紫色

注意：命令需要 @机器人 才会触发。
""".strip()

# --- Data Loading ---
card_data = {} # Removed type hint Dict[str, Dict[str, Any]]
data_file = Path(__file__).parent / "card.json"

# Color mapping from Chinese to English used in JSON
COLOR_MAP = { # Removed type hint
    "红色": "red",
    "橙色": "orange",
    "黄色": "yellow",
    "绿色": "green",
    "蓝色": "blue",
    "靛色": "indigo",
    "紫色": "purple",
}
# Reverse map for display purposes if needed, or just use the input color
COLOR_MAP_REVERSE = {v: k for k, v in COLOR_MAP.items()} # Removed type hint

# Base CSS friendly color values (still useful for text contrast logic)
HTML_COLORS = { # Removed type hint
    "red": "#E74C3C",
    "orange": "#E67E22",
    "yellow": "#F1C40F",
    "green": "#2ECC71",
    "blue": "#3498DB",
    "indigo": "#34495E", # Indigo often represented dark blue/grey in web
    "purple": "#9B59B6",
    "default": "#BDC3C7", # Default grey
}

# --- NEW: Define background patterns using CSS gradients ---
# We'll layer a semi-transparent pattern over the base color.
# Using rgba(255, 255, 255, 0.1) for a subtle light pattern
# or rgba(0, 0, 0, 0.1) for a subtle dark pattern.
PATTERN_BACKGROUNDS = {
    "red": f"linear-gradient(45deg, rgba(255, 255, 255, 0.1) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, 0.1) 50%, rgba(255, 255, 255, 0.1) 75%, transparent 75%, transparent), {HTML_COLORS['red']}", # Diagonal stripes
    "orange": f"radial-gradient(rgba(255, 255, 255, 0.1) 15%, transparent 16%) 0 0, radial-gradient(rgba(255, 255, 255, 0.1) 15%, transparent 16%) 8px 8px, {HTML_COLORS['orange']}", # Polka dots
    "yellow": f"linear-gradient(90deg, rgba(0, 0, 0, 0.05) 50%, transparent 50%), linear-gradient(rgba(0, 0, 0, 0.05) 50%, transparent 50%), {HTML_COLORS['yellow']}", # Subtle Checkers (darker pattern for light bg)
    "green": f"linear-gradient(0deg, rgba(255, 255, 255, 0.08) 50%, transparent 50%), {HTML_COLORS['green']}", # Horizontal Stripes
    "blue": f"linear-gradient(90deg, rgba(255, 255, 255, 0.08) 50%, transparent 50%), {HTML_COLORS['blue']}", # Vertical Stripes
    "indigo": f"linear-gradient(45deg, rgba(255, 255, 255, 0.05) 48%, transparent 48%), linear-gradient(-45deg, rgba(255, 255, 255, 0.05) 48%, transparent 48%), {HTML_COLORS['indigo']}", # Subtle Crosshatch
    "purple": f"linear-gradient(135deg, rgba(255, 255, 255, 0.1) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, 0.1) 50%, rgba(255, 255, 255, 0.1) 75%, transparent 75%, transparent), {HTML_COLORS['purple']}", # Opposite Diagonal stripes
    "default": f"{HTML_COLORS['default']}" # No pattern for default
}
# Add background-size for patterns that need it (dots, checkers, stripes)
PATTERN_SIZES = {
    "red": "15px 15px",
    "orange": "16px 16px",
    "yellow": "12px 12px",
    "green": "10px 10px",
    "blue": "10px 10px",
    "indigo": "8px 8px",
    "purple": "15px 15px",
}


def load_card_data():
    global card_data
    if not data_file.exists():
        logger.error(f"Card data file not found: {data_file}")
        card_data = {}
        return False
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            card_data = json.load(f)
        logger.info(f"Successfully loaded {len(card_data)} cards from {data_file}")
        return True
    except json.JSONDecodeError:
        logger.exception(f"Failed to parse JSON from {data_file}")
        card_data = {}
        return False
    except Exception as e:
        logger.exception(f"An unexpected error occurred while loading {data_file}")
        card_data = {}
        return False

# Load data when the plugin loads
load_card_data()

# --- Command Definition ---
# Apply the to_me() rule here to ensure commands only trigger when the bot is mentioned
rainbow_card_matcher = on_command("彩虹卡", aliases={"rainbowcard"}, rule=to_me(), priority=10, block=True)

# --- Helper Functions ---
async def generate_card_image(card_info): # Removed type hints: card_info: Dict[str, Any], return Optional[bytes]
    """Generates an image for the given card info using htmlrender with patterns."""
    if not html_to_pic:
        logger.error("htmlrender is not available. Cannot generate image.")
        return None

    color_en = card_info.get("color", "default") # Use 'default' if color missing
    # Get the base color for text contrast decision
    base_bg_color = HTML_COLORS.get(color_en, HTML_COLORS["default"])
    # Get the full background style (color + pattern)
    background_style = PATTERN_BACKGROUNDS.get(color_en, PATTERN_BACKGROUNDS["default"])
    # Get background size if needed for the pattern
    background_size_style = PATTERN_SIZES.get(color_en, "")
    background_size_css = f"background-size: {background_size_style};" if background_size_style else ""


    en_words = card_info.get("en_words", "").strip()
    ch_words = card_info.get("ch_words", "").strip()

    # Determine text color based on the *base* background color for better contrast
    text_color = "#FFFFFF" # Default white
    # Yellow and Orange are light enough to potentially need dark text
    if color_en in ["yellow", "orange"]:
         text_color = "#2C3E50" # Dark grey/blue

    # Handle empty English words gracefully
    en_html = f'<p class="en">{en_words}</p>' if en_words else ''

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700&family=Roboto:wght@400;700&display=swap');
            body {{
                margin: 0;
                font-family: 'Roboto', 'Noto Sans SC', sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 250px; /* Ensure body is at least card height */
            }}
            .card {{
                /* --- Use the combined background style --- */
                background: {background_style};
                {background_size_css} /* Add size if applicable */
                color: {text_color};
                width: 350px; /* Approx poker card aspect ratio, horizontal */
                height: 250px;
                border-radius: 15px;
                padding: 25px; /* Slightly more padding */
                display: flex;
                flex-direction: column;
                justify-content: center; /* Center content vertically */
                align-items: center; /* Center content horizontally */
                text-align: center;
                box-shadow: 0 6px 12px rgba(0,0,0,0.25); /* Slightly stronger shadow */
                overflow: hidden; /* Prevent text overflow */
                box-sizing: border-box; /* Include padding in width/height */
                position: relative; /* Needed for potential future overlays */
            }}
            /* Add a subtle inner shadow for depth */
            .card::before {{
                content: '';
                position: absolute;
                top: 0; left: 0; right: 0; bottom: 0;
                border-radius: 15px; /* Match parent */
                box-shadow: inset 0 0 15px rgba(0,0,0,0.15);
                pointer-events: none; /* Don't interfere with text selection */
            }}
            .ch {{
                font-size: 1.2em;
                font-weight: bold;
                margin-bottom: 15px; /* Space between CH and EN */
                /* Add slight text shadow for readability over patterns */
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
            }}
            .en {{
                font-size: 0.9em;
                font-style: italic;
                opacity: 0.95; /* Slightly less transparent */
                 /* Add slight text shadow */
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
            }}
             p {{
                margin: 5px 0; /* Adjust paragraph spacing */
                z-index: 1; /* Ensure text is above pseudo-elements */
                position: relative; /* Needed for z-index */
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <p class="ch">{ch_words}</p>
            {en_html}
        </div>
    </body>
    </html>
    """

    try:
        # Define viewport for specific dimensions matching CSS
        pic_bytes = await html_to_pic(
            html=html_content,
            viewport={"width": 350 + 2, "height": 250 + 2} # Add slight buffer for potential rendering edges
        )
        return pic_bytes
    except Exception as e:
        logger.exception("Failed to generate card image with htmlrender")
        return None

def get_random_card(color=None): # Removed type hints: color: Optional[str], return Tuple[Optional[str], Optional[Dict[str, Any]]]
    """Gets a random card, optionally filtered by color."""
    if not card_data:
        return None, None

    valid_cards = []
    if color:
        target_color_en = COLOR_MAP.get(color)
        if not target_color_en:
            return None, None # Invalid color requested
        for card_id, info in card_data.items():
            # Use .get with a default to handle cards missing color key
            if info.get("color", "default") == target_color_en:
                valid_cards.append((card_id, info))
    else:
        valid_cards = list(card_data.items())

    if not valid_cards:
        return None, None # No cards found (or no cards for that color)

    selected_id, selected_info = random.choice(valid_cards)
    return selected_id, selected_info

# --- Command Handler ---
@rainbow_card_matcher.handle()
async def handle_rainbow_card(bot: Bot, event: Event, matcher: Matcher, arg: Message = CommandArg()): # Removed Bot, Event, Matcher hints (kept Message for CommandArg)
    # Reload data if it's empty (e.g., failed initial load)
    if not card_data:
        if not load_card_data():
            await matcher.finish("抱歉，彩虹卡数据加载失败，请检查日志或联系管理员。")
            return # Exit if loading fails again

    requested_color = arg.extract_plain_text().strip()
    target_color_ch = None # User's requested color in Chinese

    if requested_color:
        if requested_color in COLOR_MAP:
            target_color_ch = requested_color
        else:
            await matcher.finish(f"抱歉，没有找到名为 '{requested_color}' 的颜色。\n可用颜色：{', '.join(COLOR_MAP.keys())}")
            return

    card_id, card_info = get_random_card(color=target_color_ch)

    if not card_info:
        if target_color_ch:
            await matcher.finish(f"抱歉，没有找到 {target_color_ch} 的彩虹卡。")
        else:
            await matcher.finish("抱歉，卡池是空的！")
        return

    # Generate the image
    card_image_bytes = await generate_card_image(card_info)

    # Prepare the explanation text
    explanation = card_info.get("explain", "无解释信息。").strip()
    # Clean up double spaces often found in the explanation
    explanation = ' '.join(explanation.split())


    # Send the result
    if card_image_bytes and html_to_pic:
        # Send image and text together
        result_message = MessageSegment.image(card_image_bytes) + f"\n\n{explanation}"
        await matcher.send(result_message)
    else:
        # Fallback to text if image generation failed or htmlrender not available
        en_words = card_info.get("en_words", "").strip()
        ch_words = card_info.get("ch_words", "").strip()
        color_name = COLOR_MAP_REVERSE.get(card_info.get('color', ''), card_info.get('color', '未知颜色'))
        fallback_text = f"【{color_name}卡】\n{ch_words}"
        if en_words:
            fallback_text += f"\n\n{en_words}"
        fallback_text += f"\n\n解释：{explanation}"
        if not html_to_pic:
           fallback_text += "\n\n(提示: 未安装 'nonebot-plugin-htmlrender' 或渲染失败，无法生成图片)"
        else:
           fallback_text += "\n\n(提示: 图片生成失败，请检查后台日志)"

        await matcher.send(fallback_text)

# --- Optional: Log successful load ---
if card_data:
    logger.info("Rainbow Card plugin loaded successfully with patterns.")
else:
    logger.warning("Rainbow Card plugin loaded, but data is empty or failed to load.")