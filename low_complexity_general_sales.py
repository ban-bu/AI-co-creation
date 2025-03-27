import streamlit as st
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import cairosvg
from openai import OpenAI
from streamlit_image_coordinates import streamlit_image_coordinates
import os
import json
import time

# API配置信息 - 实际使用时应从主文件传入或使用环境变量
API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
BASE_URL = "https://api.deepbricks.ai/v1/"

# 添加ChatGPT-4o-mini API 调用函数
def get_ai_design_suggestions(prompt):
    """使用ChatGPT-4o-mini生成设计方案建议"""
    client = OpenAI(api_key=API_KEY)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """你是一位专业的T恤设计顾问。请针对用户提供的关键词或主题，提供5种不同的T恤设计方案建议，包括T恤颜色、文字内容、位置和是否需要logo等。

                必须严格按以下JSON格式输出：
                {
                  "designs": [
                    {
                      "theme": "主题名称",
                      "color": "T恤颜色(英文颜色名称)",
                      "text": "T恤上显示的文字",
                      "position": "文字/logo位置(可选：Center, Top Left, Top Right, Bottom Left, Bottom Right)",
                      "needs_logo": true/false,
                      "description": "设计概述"
                    },
                    ... 更多设计方案 ...
                  ]
                }
                
                确保每个设计方案都是独特的、有创意的，适合不同风格和场合。文字内容应该简洁有力，适合印在T恤上。
                """},
                {"role": "user", "content": f"请为'{prompt}'这个设计理念提供5种T恤设计方案，包括颜色搭配、文字内容和位置。"}
            ],
            response_format={"type": "json_object"}
        )
        
        # 解析JSON返回结果
        try:
            suggestions = json.loads(response.choices[0].message.content)
            # 验证JSON格式是否包含designs字段
            if "designs" not in suggestions or not isinstance(suggestions["designs"], list):
                # 如果格式不正确，创建一个标准格式
                return {
                    "designs": [
                        {
                            "theme": "默认设计",
                            "color": "white",
                            "text": "My Brand",
                            "position": "Center",
                            "needs_logo": False,
                            "description": "简约白色T恤，中心位置添加黑色文字。"
                        }
                    ]
                }
            return suggestions
        except json.JSONDecodeError:
            st.warning("AI返回的结果格式无效，使用默认设计建议。")
            # 返回一个默认的建议格式
            return {
                "designs": [
                    {
                        "theme": f"{prompt}设计",
                        "color": "white",
                        "text": f"{prompt}",
                        "position": "Center",
                        "needs_logo": False,
                        "description": f"基于您的'{prompt}'关键词生成的简约设计。"
                    }
                ]
            }
    except Exception as e:
        st.error(f"Error calling ChatGPT API: {e}")
        return {
            "designs": [
                {
                    "theme": "错误恢复设计",
                    "color": "white",
                    "text": "Brand Logo",
                    "position": "Center",
                    "needs_logo": True,
                    "description": "API调用出错时的备用设计方案。"
                }
            ]
        }

def generate_vector_image(prompt):
    """Generate an image based on the prompt"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    try:
        resp = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality="standard"
        )
    except Exception as e:
        st.error(f"Error calling API: {e}")
        return None

    if resp and len(resp.data) > 0 and resp.data[0].url:
        image_url = resp.data[0].url
        try:
            image_resp = requests.get(image_url)
            if image_resp.status_code == 200:
                content_type = image_resp.headers.get("Content-Type", "")
                if "svg" in content_type.lower():
                    try:
                        png_data = cairosvg.svg2png(bytestring=image_resp.content)
                        return Image.open(BytesIO(png_data)).convert("RGBA")
                    except Exception as conv_err:
                        st.error(f"Error converting SVG to PNG: {conv_err}")
                        return None
                else:
                    return Image.open(BytesIO(image_resp.content)).convert("RGBA")
            else:
                st.error(f"Failed to download image, status code: {image_resp.status_code}")
        except Exception as download_err:
            st.error(f"Error requesting image: {download_err}")
    else:
        st.error("Could not get image URL from API response.")
    return None

def draw_selection_box(image, point=None):
    """Calculate position for design placement without drawing visible selection box"""
    # Create a copy to avoid modifying the original image
    img_copy = image.copy()
    
    # Fixed box size (1024 * 0.25)
    box_size = int(1024 * 0.25)
    
    # If no position is specified, place it in the center
    if point is None:
        x1 = (image.width - box_size) // 2
        y1 = (image.height - box_size) // 2
    else:
        x1, y1 = point
        # Ensure the selection box doesn't extend beyond image boundaries
        x1 = max(0, min(x1 - box_size//2, image.width - box_size))
        y1 = max(0, min(y1 - box_size//2, image.height - box_size))
    
    # Return the image without drawing any visible box, just the position
    return img_copy, (x1, y1)

def get_selection_coordinates(point=None, image_size=None):
    """Get coordinates and dimensions of fixed-size selection box"""
    box_size = int(1024 * 0.25)
    
    if point is None and image_size is not None:
        width, height = image_size
        x1 = (width - box_size) // 2
        y1 = (height - box_size) // 2
    else:
        x1, y1 = point
        # Ensure selection box doesn't extend beyond image boundaries
        if image_size:
            width, height = image_size
            x1 = max(0, min(x1 - box_size//2, width - box_size))
            y1 = max(0, min(y1 - box_size//2, height - box_size))
    
    return (x1, y1, box_size, box_size)

def match_background_to_shirt(design_image, shirt_image):
    """Adjust design image background color to match shirt"""
    # Ensure images are in RGBA mode
    design_image = design_image.convert("RGBA")
    shirt_image = shirt_image.convert("RGBA")
    
    # Get shirt background color (assuming top-left corner color)
    shirt_bg_color = shirt_image.getpixel((0, 0))
    
    # Get design image data
    datas = design_image.getdata()
    newData = []
    
    for item in datas:
        # If pixel is transparent, keep it unchanged
        if item[3] == 0:
            newData.append(item)
        else:
            # Adjust non-transparent pixel background color to match shirt
            newData.append((shirt_bg_color[0], shirt_bg_color[1], shirt_bg_color[2], item[3]))
    
    design_image.putdata(newData)
    return design_image

# 添加一个用于改变T恤颜色的函数
def change_shirt_color(image, color_hex):
    """改变T恤的颜色"""
    # 转换十六进制颜色为RGB
    color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    
    # 创建副本避免修改原图
    colored_image = image.copy().convert("RGBA")
    
    # 获取图像数据
    data = colored_image.getdata()
    
    # 创建新数据
    new_data = []
    # 白色阈值 - 调整这个值可以控制哪些像素被视为白色/浅色并被改变
    threshold = 200
    
    for item in data:
        # 判断是否是白色/浅色区域 (RGB值都很高)
        if item[0] > threshold and item[1] > threshold and item[2] > threshold and item[3] > 0:
            # 保持原透明度，改变颜色
            new_color = (color_rgb[0], color_rgb[1], color_rgb[2], item[3])
            new_data.append(new_color)
        else:
            # 保持其他颜色不变
            new_data.append(item)
    
    # 更新图像数据
    colored_image.putdata(new_data)
    return colored_image

def get_preset_logos():
    """获取预设logo文件夹中的所有图片"""
    logos_dir = "logos"
    preset_logos = []
    
    # 检查logos文件夹是否存在
    if not os.path.exists(logos_dir):
        os.makedirs(logos_dir)
        return preset_logos
    
    # 获取所有支持的图片文件
    for file in os.listdir(logos_dir):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            preset_logos.append(os.path.join(logos_dir, file))
    
    return preset_logos

# 添加一个新函数用于解析设计提示并返回解析结果
def parse_design_prompt(prompt):
    """解析设计提示，提取颜色、logo和文字信息"""
    design_info = {
        "text": "",
        "color": "#FFFFFF",  # 默认白色
        "logo": None,
        "position": "Center",  # 默认中心位置
        "text_color": "#000000"  # 默认黑色文字
    }
    
    # 尝试提取颜色信息
    color_keywords = {
        "白色": "#FFFFFF", "白": "#FFFFFF", "white": "#FFFFFF",
        "黑色": "#000000", "黑": "#000000", "black": "#000000",
        "红色": "#FF0000", "红": "#FF0000", "red": "#FF0000",
        "蓝色": "#0000FF", "蓝": "#0000FF", "blue": "#0000FF",
        "绿色": "#00FF00", "绿": "#00FF00", "green": "#00FF00",
        "黄色": "#FFFF00", "黄": "#FFFF00", "yellow": "#FFFF00",
        "紫色": "#800080", "紫": "#800080", "purple": "#800080",
        "粉色": "#FFC0CB", "粉红": "#FFC0CB", "pink": "#FFC0CB",
        "灰色": "#808080", "灰": "#808080", "gray": "#808080", "grey": "#808080",
        "青色": "#00FFFF", "青": "#00FFFF", "cyan": "#00FFFF",
        "橙色": "#FFA500", "橙": "#FFA500", "orange": "#FFA500",
        "棕色": "#A52A2A", "棕": "#A52A2A", "brown": "#A52A2A"
    }
    
    # 先用整个词匹配
    for color_name, color_hex in color_keywords.items():
        if color_name in prompt.lower():
            design_info["color"] = color_hex
            break

    # 提取t恤/T恤/tshirt等关键词之前的颜色信息
    import re
    color_t_match = re.search(r'([a-zA-Z\u4e00-\u9fa5]+)\s*[tT]恤', prompt)
    if color_t_match:
        color_name = color_t_match.group(1).lower().strip()
        if color_name in color_keywords:
            design_info["color"] = color_keywords[color_name]
    
    # 尝试提取位置信息
    position_keywords = {
        "中心": "Center", "中央": "Center", "center": "Center", "中间": "Center", "居中": "Center",
        "左上": "Top Left", "top left": "Top Left", "左上角": "Top Left", "左上方": "Top Left",
        "右上": "Top Right", "top right": "Top Right", "右上角": "Top Right", "右上方": "Top Right",
        "左下": "Bottom Left", "bottom left": "Bottom Left", "左下角": "Bottom Left", "左下方": "Bottom Left",
        "右下": "Bottom Right", "bottom right": "Bottom Right", "右下角": "Bottom Right", "右下方": "Bottom Right",
        "顶部": "Top Center", "top": "Top Center", "上方": "Top Center", "上部": "Top Center", "上边": "Top Center",
        "底部": "Bottom Center", "bottom": "Bottom Center", "下方": "Bottom Center", "下部": "Bottom Center", "下边": "Bottom Center",
        "左侧": "Middle Left", "左边": "Middle Left", "left": "Middle Left",
        "右侧": "Middle Right", "右边": "Middle Right", "right": "Middle Right"
    }
    
    for pos_name, pos_value in position_keywords.items():
        if pos_name in prompt.lower():
            design_info["position"] = pos_value
            break
    
    # 尝试提取文字内容 - 多种模式匹配
    import re
    
    # 尝试匹配单引号或双引号包围的内容
    text_patterns = [
        r'["\'](.*?)["\']',  # 引号内的内容
        r'文字[：:]?\s*["\'](.*?)["\']',  # "文字:"后引号内的内容
        r'文字[：:]?\s*([^\s,，.。]+)',  # "文字:"后的单个词
        r'text[：:]?\s*["\'](.*?)["\']',  # "text:"后引号内的内容
        r'text[：:]?\s*([^\s,，.。]+)',  # "text:"后的单个词 
        r'添加[：:]?\s*["\'](.*?)["\']',  # "添加:"后引号内的内容
        r'印[：:]?\s*["\'](.*?)["\']',  # "印:"后引号内的内容
        r'写[：:]?\s*["\'](.*?)["\']',  # "写:"后引号内的内容
    ]
    
    # 尝试所有模式
    for pattern in text_patterns:
        text_match = re.search(pattern, prompt, re.IGNORECASE)
        if text_match:
            design_info["text"] = text_match.group(1)
            break
    
    # 如果上面的方法都没找到文字，尝试查找'添加'或'印上'后面的内容
    if not design_info["text"]:
        text_phrases = [
            r'添加\s*([\u4e00-\u9fa5a-zA-Z0-9]+)',
            r'印上\s*([\u4e00-\u9fa5a-zA-Z0-9]+)',
            r'印制\s*([\u4e00-\u9fa5a-zA-Z0-9]+)',
            r'显示\s*([\u4e00-\u9fa5a-zA-Z0-9]+)'
        ]
        
        for pattern in text_phrases:
            text_match = re.search(pattern, prompt)
            if text_match:
                design_info["text"] = text_match.group(1)
                break
    
    # 提取可能的logo引用
    logo_keywords = ["logo", "图标", "标志", "图样", "图案", "商标", "标识"]
    for keyword in logo_keywords:
        if keyword in prompt.lower():
            # 如果找到logo关键词，设置为需要选择logo
            design_info["needs_logo"] = True
            break
    
    # 如果没有提取到任何文字但提到了logo，设置一个默认文字
    if not design_info["text"] and design_info.get("needs_logo", False):
        design_info["text"] = "Brand"
    
    # 根据T恤颜色自动调整文字颜色以增加对比度
    dark_colors = ["#000000", "#0000FF", "#800080", "#A52A2A", "#808080", "#FF0000"]
    if design_info["color"] in dark_colors:
        design_info["text_color"] = "#FFFFFF"  # 暗色T恤用白色文字
    else:
        design_info["text_color"] = "#000000"  # 亮色T恤用黑色文字
    
    return design_info

# AI Customization Group design page
def show_low_complexity_general_sales():
    st.title("👕 AI Co-Creation Experiment Platform")
    st.markdown("### Low Task Complexity-General Sales - Create Your Unique T-shirt Design")
    
    # 添加General Sales情境描述
    st.info("""
    **General Sales Environment**
    
    Welcome to our regular T-shirt customization service available in our standard online store. 
    You are browsing our website from the comfort of your home or office, with no time pressure. 
    Take your time to explore the design options and create a T-shirt that matches your personal style.
    This is a typical online shopping experience where you can customize at your own pace.
    """)
    
    # 任务复杂度说明
    st.markdown("""
    <div style="background-color:#f0f0f0; padding:10px; border-radius:5px; margin-bottom:15px">
    <b>Basic Customization Options</b>: In this experience, you can customize your T-shirt with simple options:
    <ul>
        <li>描述您想要的T恤设计</li>
        <li>选择推荐设计或自定义设计</li>
        <li>添加文字和选择位置</li>
        <li>添加logo（可选）</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # 初始化T恤颜色状态变量
    if 'shirt_color_hex' not in st.session_state:
        st.session_state.shirt_color_hex = "#FFFFFF"  # 默认白色
    if 'original_base_image' not in st.session_state:
        st.session_state.original_base_image = None  # 保存原始白色T恤图像
    # 初始化AI设计建议相关变量    
    if 'design_suggestions' not in st.session_state:
        st.session_state.design_suggestions = []  # 存储AI生成的设计建议
    if 'selected_prompt' not in st.session_state:
        st.session_state.selected_prompt = ""  # 存储用户选择的设计提示词
    if 'design_step' not in st.session_state:
        st.session_state.design_step = "input_prompt"  # 设计步骤: input_prompt, customize, apply_design
    
    # Create two-column layout
    col1, col2 = st.columns([2, 3])
    
    with col1:
        st.markdown("## AI设计助手")
        
        # 显示新的设计流程说明
        st.markdown("""
        <div style="background-color:#e8f4f8; padding:15px; border-radius:10px; margin-bottom:20px; border-left:5px solid #2e86c1;">
        <h4 style="color:#2e86c1; margin-top:0;">🆕 全新设计流程</h4>
        <ol>
            <li>输入您想要的T恤设计描述</li>
            <li>获取AI设计建议</li>
            <li>选择或自定义颜色、文字和logo</li>
            <li>应用设计查看效果</li>
        </ol>
        </div>
        """, unsafe_allow_html=True)
        
        # 用户输入设计描述
        st.markdown("### 1. 描述您想要的T恤设计")
        design_idea = st.text_area(
            "输入设计描述:",
            value=st.session_state.get("selected_prompt", ""),
            placeholder="例如：蓝色T恤，前胸居中添加'CODER'文字",
            help="描述您想要的T恤设计，包括颜色、文字内容和位置等",
            height=100
        )
        
        # 添加设计描述示例
        st.markdown("""
        <div style="background-color:#f0f0f0; padding:8px; border-radius:5px; margin:5px 0 15px 0; font-size:0.9em;">
        <strong>设计描述示例:</strong>
        <ul style="margin-top:5px; margin-bottom:5px;">
          <li>黑色T恤，中心位置添加"CODER"文字</li>
          <li>蓝色T恤，左上角添加logo，底部添加"Ocean"文字</li>
          <li>红色T恤，右上位置添加"2024"文字</li>
          <li>夏日海滩主题的T恤设计</li>
          <li>网络朋克风格的T恤</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # AI设计建议按钮
        if st.button("🎨 获取AI设计建议", key="get_ai_suggestions", use_container_width=True):
            if not design_idea.strip():
                st.warning("请输入设计描述或主题!")
            else:
                with st.spinner("AI正在生成设计方案..."):
                    # 保存用户输入的提示词
                    st.session_state.selected_prompt = design_idea
                    
                    # 首先尝试直接解析用户输入
                    design_info = parse_design_prompt(design_idea)
                    
                    # 如果输入更像主题而非具体设计描述，则调用AI生成设计建议
                    if not design_info["text"] and design_info["color"] == "#FFFFFF":
                        # 调用AI生成设计建议
                        suggestions = get_ai_design_suggestions(design_idea)
                        
                        if suggestions and "designs" in suggestions:
                            # 保存建议到session state
                            st.session_state.design_suggestions = suggestions["designs"]
                        else:
                            st.error("无法生成设计建议。请稍后再试。")
                    else:
                        # 用户输入了具体设计描述，创建一个设计建议
                        st.session_state.design_suggestions = [{
                            "theme": "您的设计",
                            "color": design_info["color"].replace("#", ""),
                            "text": design_info["text"],
                            "position": design_info["position"],
                            "needs_logo": design_info.get("needs_logo", False),
                            "description": f"根据您的描述'{design_idea}'解析的设计方案"
                        }]
                    
                    # 更新设计步骤为自定义
                    st.session_state.design_step = "customize"
                    st.rerun()
        
        # 如果已有设计建议，显示它们
        if st.session_state.design_suggestions:
            st.markdown("### 2. AI设计建议")
            
            for i, design in enumerate(st.session_state.design_suggestions):
                with st.container():
                    # 为每个设计建议创建彩色卡片效果
                    # 获取颜色对应的十六进制值用于显示
                    color_name = design.get('color', 'white').lower()
                    color_hex = {
                        "white": "#FFFFFF", "black": "#000000", "red": "#FF0000",
                        "blue": "#0000FF", "green": "#00FF00", "yellow": "#FFFF00",
                        "purple": "#800080", "pink": "#FFC0CB", "gray": "#808080",
                        "cyan": "#00FFFF", "orange": "#FFA500", "brown": "#A52A2A"
                    }.get(color_name, "#FFFFFF")
                    
                    # 文本颜色应该与T恤颜色形成对比
                    text_preview_color = "#000000" if color_name in ["white", "yellow", "cyan", "pink"] else "#FFFFFF"
                    
                    st.markdown(f"""
                    <div style="border:1px solid #ddd; padding:15px; margin:8px 0; border-radius:10px; 
                         background-color:rgba(240,248,255,0.6); box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
                    <h4 style="color:#1E90FF; margin-top:0;">设计 {i+1}: {design.get('theme', '自定义设计')}</h4>
                    <div style="display:flex; margin-bottom:10px;">
                      <div style="width:40px; height:40px; background-color:{color_hex}; border:1px solid #ddd; border-radius:5px;"></div>
                      <div style="margin-left:10px;">
                        <strong>颜色:</strong> {design.get('color', 'white')}
                      </div>
                    </div>
                    <div style="background-color:{color_hex}; padding:10px; border-radius:5px; text-align:center; margin-bottom:10px;">
                      <span style="color:{text_preview_color}; font-weight:bold;">{design.get('text', '')}</span>
                    </div>
                    <p><strong>位置:</strong> {design.get('position', 'Center')}</p>
                    <p><strong>Logo:</strong> {"需要" if design.get('needs_logo', False) else "不需要"}</p>
                    <p style="font-style:italic;">{design.get('description', '')}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 将此设计用作基础的按钮
                    if st.button(f"✨ 选择设计 {i+1}", key=f"use_design_{i}"):
                        # 设置颜色
                        color_hex_value = color_hex
                        st.session_state.shirt_color_hex = color_hex_value
                        
                        # 设置文字
                        st.session_state.selected_text = design.get('text', '')
                        
                        # 设置位置
                        st.session_state.selected_position = design.get('position', 'Center')
                        
                        # 设置是否需要logo
                        st.session_state.needs_logo = design.get('needs_logo', False)
                        
                        # 重新着色T恤图像
                        if st.session_state.original_base_image is not None:
                            new_colored_image = change_shirt_color(st.session_state.original_base_image, color_hex_value)
                            st.session_state.base_image = new_colored_image
                            
                            # 更新当前图像
                            new_current_image, _ = draw_selection_box(new_colored_image, st.session_state.current_box_position)
                            st.session_state.current_image = new_current_image
                        
                        # 更新设计步骤
                        st.session_state.design_step = "customize"
                        st.rerun()
                        
            # 自定义设计部分
            if st.session_state.design_step == "customize":
                st.markdown("### 3. 自定义设计")
                
                # T恤颜色选择
                st.subheader("T恤颜色")
                color_col1, color_col2 = st.columns([1, 3])
                with color_col1:
                    # 显示当前颜色预览
                    st.markdown(
                        f"""
                        <div style="background-color:{st.session_state.shirt_color_hex};
                        width:50px; height:50px; border-radius:5px; border:1px solid #ddd;"></div>
                        """,
                        unsafe_allow_html=True
                    )
                with color_col2:
                    shirt_color = st.color_picker("选择颜色:", st.session_state.shirt_color_hex)
                
                # 处理颜色变化
                if shirt_color != st.session_state.shirt_color_hex:
                    st.session_state.shirt_color_hex = shirt_color
                    
                    # 重新着色T恤图像
                    if st.session_state.original_base_image is not None:
                        # 对原始白色T恤应用新颜色
                        new_colored_image = change_shirt_color(st.session_state.original_base_image, shirt_color)
                        st.session_state.base_image = new_colored_image
                        
                        # 更新当前图像（带红框的）
                        new_current_image, _ = draw_selection_box(new_colored_image, st.session_state.current_box_position)
                        st.session_state.current_image = new_current_image
                        
                        # 如果有最终设计，也需要更新
                        if st.session_state.final_design is not None:
                            # 重置最终设计，让用户重新应用设计元素
                            st.session_state.final_design = None
                
                # 文字内容设置
                st.subheader("文字设置")
                text_content = st.text_input(
                    "文字内容:", 
                    value=st.session_state.get("selected_text", ""),
                    placeholder="输入要显示在T恤上的文字"
                )
                
                # 文字位置
                text_position_options = {
                    "Center": "居中",
                    "Top Left": "左上角",
                    "Top Right": "右上角",
                    "Bottom Left": "左下角",
                    "Bottom Right": "右下角",
                    "Top Center": "顶部居中",
                    "Bottom Center": "底部居中"
                }
                position_values = list(text_position_options.keys())
                position_labels = list(text_position_options.values())
                
                default_index = position_values.index(st.session_state.get("selected_position", "Center"))
                text_position = st.selectbox(
                    "文字位置:", 
                    options=range(len(position_values)),
                    format_func=lambda i: position_labels[i],
                    index=default_index
                )
                selected_position = position_values[text_position]
                
                # 文字颜色
                # 根据T恤颜色自动选择对比色
                dark_colors = ["#000000", "#0000FF", "#800080", "#A52A2A", "#808080", "#FF0000"]
                if st.session_state.shirt_color_hex in dark_colors:
                    default_text_color = "#FFFFFF"  # 暗色T恤用白色文字
                else:
                    default_text_color = "#000000"  # 亮色T恤用黑色文字
                
                text_color = st.color_picker("文字颜色:", default_text_color)
                
                # Logo选项
                st.subheader("Logo设置")
                need_logo = st.checkbox("添加Logo", value=st.session_state.get("needs_logo", False))
                
                if need_logo:
                    # Logo来源选择
                    logo_source = st.radio("Logo来源:", ["上传Logo", "选择预设Logo"], horizontal=True)
                    
                    if logo_source == "上传Logo":
                        # Logo上传选项
                        uploaded_logo = st.file_uploader("上传您的Logo (PNG或JPG文件):", type=["png", "jpg", "jpeg"])
                        if uploaded_logo is not None:
                            try:
                                # 显示上传的logo预览
                                logo_preview = Image.open(BytesIO(uploaded_logo.getvalue())).convert("RGBA")
                                st.image(logo_preview, width=150, caption="上传的Logo预览")
                                st.session_state.selected_logo = uploaded_logo.getvalue()
                                st.session_state.logo_type = "uploaded"
                            except Exception as e:
                                st.error(f"加载Logo出错: {e}")
                    else:  # 选择预设Logo
                        # 获取预设logo
                        preset_logos = get_preset_logos()
                        
                        if not preset_logos:
                            st.warning("未找到预设Logo。请在'logos'文件夹中添加图片。")
                        else:
                            # 显示预设logo选择
                            st.write("选择一个预设Logo:")
                            logo_cols = st.columns(min(3, len(preset_logos)))
                            
                            for i, logo_path in enumerate(preset_logos):
                                with logo_cols[i % 3]:
                                    logo_name = os.path.basename(logo_path)
                                    try:
                                        logo_preview = Image.open(logo_path).convert("RGBA")
                                        # 调整预览大小
                                        preview_width = 80
                                        preview_height = int(preview_width * logo_preview.height / logo_preview.width)
                                        preview = logo_preview.resize((preview_width, preview_height))
                                        
                                        st.image(preview, caption=logo_name)
                                        if st.button(f"选择", key=f"logo_{i}"):
                                            st.session_state.selected_logo = logo_path
                                            st.session_state.logo_type = "preset"
                                            st.rerun()
                                    except Exception as e:
                                        st.error(f"加载Logo {logo_name}出错: {e}")
                    
                    # Logo大小
                    logo_size = st.slider("Logo大小:", 10, 100, 40, format="%d%%")
                    
                    # Logo位置
                    logo_position_options = {
                        "Center": "居中",
                        "Top Left": "左上角",
                        "Top Right": "右上角",
                        "Bottom Left": "左下角",
                        "Bottom Right": "右下角",
                        "Top Center": "顶部居中",
                        "Bottom Center": "底部居中"
                    }
                    logo_position_values = list(logo_position_options.keys())
                    logo_position_labels = list(logo_position_options.values())
                    
                    default_logo_index = 0  # 默认居中
                    logo_position = st.selectbox(
                        "Logo位置:", 
                        options=range(len(logo_position_values)),
                        format_func=lambda i: logo_position_labels[i],
                        index=default_logo_index,
                        key="logo_position"
                    )
                    selected_logo_position = logo_position_values[logo_position]
                    
                    # Logo透明度
                    logo_opacity = st.slider("Logo透明度:", 10, 100, 100, 5, format="%d%%")
                
                # 应用设计按钮
                st.markdown("### 4. 完成设计")
                if st.button("✅ 应用设计", key="apply_design_button", use_container_width=True):
                    if not text_content.strip() and not need_logo:
                        st.warning("请至少添加文字内容或Logo!")
                    else:
                        # 创建进度显示区
                        progress_container = st.empty()
                        progress_container.info("🔍 正在应用您的设计...")
                        
                        # 创建设计复合图像
                        composite_image = st.session_state.base_image.copy()
                        
                        # 如果有文字内容，添加到设计中
                        if text_content.strip():
                            progress_container.info("✍️ 添加文字到设计...")
                            # 准备绘图对象
                            draw = ImageDraw.Draw(composite_image)
                            
                            try:
                                # 使用默认字体
                                from PIL import ImageFont
                                try:
                                    # 尝试加载合适的字体
                                    font = ImageFont.truetype("arial.ttf", 48)
                                except:
                                    # 如果失败，使用默认字体
                                    font = ImageFont.load_default()
                            
                                # 获取当前选择框位置
                                left, top = st.session_state.current_box_position
                                box_size = int(1024 * 0.25)
                                
                                # 计算文字位置 - 根据设计信息中的位置
                                text_bbox = draw.textbbox((0, 0), text_content, font=font)
                                text_width = text_bbox[2] - text_bbox[0]
                                text_height = text_bbox[3] - text_bbox[1]
                                
                                # 根据position确定文字位置
                                if selected_position == "Center":
                                    text_x = left + (box_size - text_width) // 2
                                    text_y = top + (box_size - text_height) // 2
                                elif selected_position == "Top Left":
                                    text_x = left + 10
                                    text_y = top + 10
                                elif selected_position == "Top Right":
                                    text_x = left + box_size - text_width - 10
                                    text_y = top + 10
                                elif selected_position == "Bottom Left":
                                    text_x = left + 10
                                    text_y = top + box_size - text_height - 10
                                elif selected_position == "Bottom Right":
                                    text_x = left + box_size - text_width - 10
                                    text_y = top + box_size - text_height - 10
                                elif selected_position == "Top Center":
                                    text_x = left + (box_size - text_width) // 2
                                    text_y = top + 10
                                else:  # "Bottom Center"
                                    text_x = left + (box_size - text_width) // 2
                                    text_y = top + box_size - text_height - 10
                                
                                # 使用设计信息中的文字颜色
                                draw.text((text_x, text_y), text_content, fill=text_color, font=font)
                            except Exception as e:
                                st.warning(f"添加文字出错: {e}")
                        
                        # 如果需要添加Logo
                        if need_logo and hasattr(st.session_state, 'selected_logo'):
                            progress_container.info("🖼️ 添加Logo到设计...")
                            try:
                                # 根据Logo类型处理
                                if st.session_state.logo_type == "uploaded":
                                    logo_image = Image.open(BytesIO(st.session_state.selected_logo)).convert("RGBA")
                                else:  # preset
                                    logo_image = Image.open(st.session_state.selected_logo).convert("RGBA")
                                
                                # 调整Logo大小
                                box_size = int(1024 * 0.25)
                                logo_width = int(box_size * logo_size / 100)
                                logo_height = int(logo_width * logo_image.height / logo_image.width)
                                logo_resized = logo_image.resize((logo_width, logo_height), Image.LANCZOS)
                                
                                # 获取选择框位置
                                left, top = st.session_state.current_box_position
                                
                                # 计算Logo位置
                                if selected_logo_position == "Top Left":
                                    logo_x, logo_y = left + 10, top + 10
                                elif selected_logo_position == "Top Center":
                                    logo_x, logo_y = left + (box_size - logo_width) // 2, top + 10
                                elif selected_logo_position == "Top Right":
                                    logo_x, logo_y = left + box_size - logo_width - 10, top + 10
                                elif selected_logo_position == "Center":
                                    logo_x, logo_y = left + (box_size - logo_width) // 2, top + (box_size - logo_height) // 2
                                elif selected_logo_position == "Bottom Left":
                                    logo_x, logo_y = left + 10, top + box_size - logo_height - 10
                                elif selected_logo_position == "Bottom Center":
                                    logo_x, logo_y = left + (box_size - logo_width) // 2, top + box_size - logo_height - 10
                                else:  # Bottom Right
                                    logo_x, logo_y = left + box_size - logo_width - 10, top + box_size - logo_height - 10
                                
                                # 设置透明度
                                if logo_opacity < 100:
                                    logo_data = logo_resized.getdata()
                                    new_data = []
                                    for item in logo_data:
                                        r, g, b, a = item
                                        new_a = int(a * logo_opacity / 100)
                                        new_data.append((r, g, b, new_a))
                                    logo_resized.putdata(new_data)
                                
                                # 粘贴Logo到设计
                                composite_image.paste(logo_resized, (logo_x, logo_y), logo_resized)
                            except Exception as e:
                                st.warning(f"添加Logo出错: {e}")
                        
                        # 更新设计
                        st.session_state.final_design = composite_image
                        
                        # 同时更新current_image以便在T恤图像上直接显示设计
                        st.session_state.current_image = composite_image.copy()
                        
                        # 清除进度消息并显示成功消息
                        progress_container.success("🎉 设计已成功应用到您的T恤!")
                        
                        # 更新设计步骤
                        st.session_state.design_step = "completed"
                        st.rerun()
    
    with col2:
        st.markdown("## 设计预览")
        
        # Load T-shirt base image
        if 'base_image' not in st.session_state or st.session_state.base_image is None:
            try:
                # 加载原始白色T恤图像
                original_image = Image.open("white_shirt.png").convert("RGBA")
                # 保存原始白色T恤图像
                st.session_state.original_base_image = original_image.copy()
                
                # 应用当前选择的颜色
                colored_image = change_shirt_color(original_image, st.session_state.shirt_color_hex)
                st.session_state.base_image = colored_image
                
                # Initialize by drawing selection box in the center
                initial_image, initial_pos = draw_selection_box(colored_image)
                st.session_state.current_image = initial_image
                st.session_state.current_box_position = initial_pos
            except Exception as e:
                st.error(f"加载T恤图像出错: {e}")
                st.stop()
        
        # Display current image and get click coordinates
        current_image = st.session_state.current_image
        coordinates = streamlit_image_coordinates(
            current_image,
            key="shirt_image"
        )
        
        # Handle selection area logic - simplify to directly move red box
        if coordinates:
            # Update selection box at current mouse position
            current_point = (coordinates["x"], coordinates["y"])
            temp_image, new_pos = draw_selection_box(st.session_state.base_image, current_point)
            st.session_state.current_image = temp_image
            st.session_state.current_box_position = new_pos
            st.rerun()
        
        st.info("👆 点击T恤上的任意位置选择设计元素放置区域")
            
        # 最终设计结果显示
        if st.session_state.design_step == "completed" and st.session_state.final_design is not None:
            st.markdown("### 最终设计")
            
            # 添加清空设计按钮
            if st.button("🗑️ 清空设计", key="clear_designs"):
                # 清空所有设计相关的状态变量
                st.session_state.generated_design = None
                # 重置最终设计为基础T恤图像
                st.session_state.final_design = None
                # 重置当前图像为带选择框的基础图像
                temp_image, _ = draw_selection_box(st.session_state.base_image, st.session_state.current_box_position)
                st.session_state.current_image = temp_image
                # 重置设计步骤
                st.session_state.design_step = "input_prompt"
                st.rerun()
            
            # 添加T恤规格信息
            # 显示当前颜色
            color_name = {
                "#FFFFFF": "白色",
                "#000000": "黑色",
                "#FF0000": "红色",
                "#00FF00": "绿色",
                "#0000FF": "蓝色",
                "#FFFF00": "黄色",
                "#FF00FF": "品红",
                "#00FFFF": "青色",
                "#C0C0C0": "银色",
                "#808080": "灰色",
                "#FFA500": "橙色",
                "#A52A2A": "棕色"
            }.get(st.session_state.shirt_color_hex.upper(), "自定义")
            
            # 创建规格卡片
            st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; margin:10px 0; border:1px solid #ddd;">
            <h4 style="margin-top:0;">T恤规格</h4>
            <p><strong>颜色:</strong> {color_name} ({st.session_state.shirt_color_hex})</p>
            <p><strong>规格:</strong> 标准尺寸，100%棉</p>
            <p><strong>定制:</strong> 个性化文字/Logo设计</p>
            </div>
            """, unsafe_allow_html=True)
            
            # 提供下载选项
            download_col1, download_col2 = st.columns(2)
            with download_col1:
                buf = BytesIO()
                st.session_state.final_design.save(buf, format="PNG")
                buf.seek(0)
                st.download_button(
                    label="💾 下载设计",
                    data=buf,
                    file_name="custom_tshirt.png",
                    mime="image/png"
                )
            
            with download_col2:
                # 确认完成按钮
                if st.button("✅ 确认完成", key="confirm_button"):
                    st.session_state.page = "survey"
                    st.rerun()
    
    # Return to main interface button
    if st.button("返回主页"):
        # Clear all design-related states
        st.session_state.base_image = None
        st.session_state.current_image = None
        st.session_state.current_box_position = None
        st.session_state.generated_design = None
        st.session_state.final_design = None
        st.session_state.design_step = "input_prompt"
        # Only change page state, retain user info and experiment group
        st.session_state.page = "welcome"
        st.rerun() 
