import streamlit as st
from PIL import Image, ImageDraw
import requests
from io import BytesIO
# 添加try-except导入cairosvg，避免因缺少这个库而导致整个应用崩溃
try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except ImportError:
    CAIROSVG_AVAILABLE = False
    # 尝试导入备选SVG处理库
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        SVGLIB_AVAILABLE = True
    except ImportError:
        SVGLIB_AVAILABLE = False
        st.warning("SVG处理库未安装，SVG格式转换功能将不可用")
from openai import OpenAI
from streamlit_image_coordinates import streamlit_image_coordinates
import os
import re

# API配置信息 - 实际使用时应从主文件传入或使用环境变量
API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
BASE_URL = "https://api.deepbricks.ai/v1/"

# GPT-4o-mini API配置
GPT4O_MINI_API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
GPT4O_MINI_BASE_URL = "https://api.deepbricks.ai/v1/"

def get_ai_design_suggestions(user_preferences=None):
    """从GPT-4o-mini获取设计建议"""
    client = OpenAI(api_key=GPT4O_MINI_API_KEY, base_url=GPT4O_MINI_BASE_URL)
    
    # 默认提示如果没有用户偏好
    if not user_preferences:
        user_preferences = "时尚休闲风格的T恤设计"
    
    # 构建提示词
    prompt = f"""
    作为T恤设计顾问，请为"{user_preferences}"风格提供以下设计建议：

    1. 颜色建议：推荐3种适合的颜色，包括：
       - 颜色名称和十六进制代码(如 蓝色 (#0000FF))
       - 为什么这种颜色适合该风格(2-3句话解释)
       
    2. 文字建议：推荐2个适合的文字/短语：
       - 具体文字内容
       - 推荐的字体风格
       - 简短说明为什么适合
       
    3. Logo元素建议：推荐2种适合的设计元素：
       - 元素描述
       - 如何与整体风格搭配
       
    确保包含颜色的十六进制代码，保持内容详实但不过于冗长。
    文字建议部分，请将每个推荐的短语/文字单独放在一行上，并使用引号包裹，例如："Just Do It"。
    """
    
    try:
        # 调用GPT-4o-mini
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一个专业的T恤设计顾问，提供有用且具体的建议。包含足够细节让用户理解你的推荐理由，但避免不必要的冗长。确保为每种颜色包含十六进制代码。对于文字建议，请将推荐的短语用引号包裹并单独放在一行。"},
                {"role": "user", "content": prompt}
            ]
        )
        
        # 返回建议内容
        if response.choices and len(response.choices) > 0:
            suggestion_text = response.choices[0].message.content
            
            # 尝试解析颜色代码
            try:
                # 提取颜色代码的简单方法
                color_matches = {}
                
                # 查找形如 "颜色名 (#XXXXXX)" 的模式
                color_pattern = r'([^\s\(\)]+)\s*\(#([0-9A-Fa-f]{6})\)'
                matches = re.findall(color_pattern, suggestion_text)
                
                if matches:
                    color_matches = {name.strip(): f"#{code}" for name, code in matches}
                    
                # 保存到会话状态
                if color_matches:
                    st.session_state.ai_suggested_colors = color_matches
                    
                # 尝试提取推荐文字
                text_pattern = r'[""]([^""]+)[""]'
                text_matches = re.findall(text_pattern, suggestion_text)
                
                # 保存推荐文字到会话状态
                if text_matches:
                    st.session_state.ai_suggested_texts = text_matches
                else:
                    # 尝试使用另一种模式匹配
                    text_pattern2 = r'"([^"]+)"'
                    text_matches = re.findall(text_pattern2, suggestion_text)
                    if text_matches:
                        st.session_state.ai_suggested_texts = text_matches
                    else:
                        st.session_state.ai_suggested_texts = []
                        
            except Exception as e:
                print(f"解析过程出错: {e}")
                st.session_state.ai_suggested_texts = []
                
            # 使用更好的排版处理文本
            # 替换标题格式
            formatted_text = suggestion_text
            # 处理序号段落
            formatted_text = re.sub(r'(\d\. .*?)(?=\n\d\. |\n*$)', r'<div class="suggestion-section">\1</div>', formatted_text)
            # 处理子项目符号
            formatted_text = re.sub(r'- (.*?)(?=\n- |\n[^-]|\n*$)', r'<div class="suggestion-item">• \1</div>', formatted_text)
            # 强调颜色名称和代码
            formatted_text = re.sub(r'([^\s\(\)]+)\s*\(#([0-9A-Fa-f]{6})\)', r'<span class="color-name">\1</span> <span class="color-code">(#\2)</span>', formatted_text)
            
            # 不再使用JavaScript回调，而是简单地加粗文本
            formatted_text = re.sub(r'[""]([^""]+)[""]', r'"<strong>\1</strong>"', formatted_text)
            formatted_text = re.sub(r'"([^"]+)"', r'"<strong>\1</strong>"', formatted_text)
            
            suggestion_with_style = f"""
            <div class="suggestion-container">
            {formatted_text}
            </div>
            """
            
            return suggestion_with_style
        else:
            return "无法获取AI建议，请稍后再试。"
    except Exception as e:
        return f"获取AI建议时出错: {str(e)}"

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
                    # 判断SVG处理库是否可用
                    if CAIROSVG_AVAILABLE:
                        try:
                            png_data = cairosvg.svg2png(bytestring=image_resp.content)
                            return Image.open(BytesIO(png_data)).convert("RGBA")
                        except Exception as conv_err:
                            st.error(f"Error converting SVG to PNG with cairosvg: {conv_err}")
                            # 尝试使用备选方案
                            if SVGLIB_AVAILABLE:
                                try:
                                    svg_data = BytesIO(image_resp.content)
                                    drawing = svg2rlg(svg_data)
                                    png_data = BytesIO()
                                    renderPM.drawToFile(drawing, png_data, fmt="PNG")
                                    png_data.seek(0)
                                    return Image.open(png_data).convert("RGBA")
                                except Exception as svg_err:
                                    st.error(f"Error converting SVG to PNG with svglib: {svg_err}")
                            return None
                    elif SVGLIB_AVAILABLE:
                        # 使用svglib作为备选
                        try:
                            svg_data = BytesIO(image_resp.content)
                            drawing = svg2rlg(svg_data)
                            png_data = BytesIO()
                            renderPM.drawToFile(drawing, png_data, fmt="PNG")
                            png_data.seek(0)
                            return Image.open(png_data).convert("RGBA")
                        except Exception as svg_err:
                            st.error(f"Error converting SVG to PNG with svglib: {svg_err}")
                            return None
                    else:
                        st.error("无法处理SVG格式，SVG处理库未安装")
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
        <li>Choose T-shirt color</li>
        <li>Add text or logo elements</li>
        <li>Generate design patterns</li>
        <li>Position your design on the T-shirt</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # 初始化T恤颜色状态变量
    if 'shirt_color_hex' not in st.session_state:
        st.session_state.shirt_color_hex = "#FFFFFF"  # 默认白色
    if 'original_base_image' not in st.session_state:
        st.session_state.original_base_image = None  # 保存原始白色T恤图像
    if 'ai_suggestions' not in st.session_state:
        st.session_state.ai_suggestions = None  # 存储AI建议
    
    # 重新组织布局，将预览图放在左侧，操作区放在右侧
    st.markdown("## Design Area")
    
    # 创建左右两列布局
    preview_col, controls_col = st.columns([1, 1])
    
    with preview_col:
        # T恤预览区
        # Load T-shirt base image
        if st.session_state.base_image is None:
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
                st.error(f"Error loading white T-shirt image: {e}")
                st.stop()
        else:
            # 添加颜色变化检测：保存当前应用的颜色，用于检查是否发生变化
            if 'current_applied_color' not in st.session_state:
                st.session_state.current_applied_color = st.session_state.shirt_color_hex
            
            # 检查颜色是否发生变化
            if st.session_state.current_applied_color != st.session_state.shirt_color_hex:
                # 颜色已变化，需要重新应用
                original_image = st.session_state.original_base_image.copy()
                colored_image = change_shirt_color(original_image, st.session_state.shirt_color_hex)
                st.session_state.base_image = colored_image
                
                # 更新当前图像和位置
                new_image, _ = draw_selection_box(colored_image, st.session_state.current_box_position)
                st.session_state.current_image = new_image
                
                # 如果有最终设计，也需要重新应用颜色
                st.session_state.final_design = colored_image.copy()
                
                # 重新应用之前的文字和Logo
                if 'applied_text' in st.session_state:
                    text_info = st.session_state.applied_text
                    draw = ImageDraw.Draw(st.session_state.final_design)
                    
                    try:
                        from PIL import ImageFont
                        font = None
                        
                        # 尝试加载字体
                        font_mapping = {
                            "Arial": "arial.ttf",
                            "Times New Roman": "times.ttf",
                            "Courier": "cour.ttf",
                            "Verdana": "verdana.ttf",
                            "Georgia": "georgia.ttf",
                            "Impact": "impact.ttf"
                        }
                        
                        system_font_paths = [
                            "/Library/Fonts/",
                            "/System/Library/Fonts/",
                            "C:/Windows/Fonts/",
                            "/usr/share/fonts/truetype/",
                        ]
                        
                        font_file = font_mapping.get(text_info["font"], "arial.ttf")
                        for path in system_font_paths:
                            try:
                                font = ImageFont.truetype(path + font_file, text_info["size"])
                                break
                            except:
                                continue
                        
                        if font is None:
                            font = ImageFont.load_default()
                            
                        # 重新计算文字位置
                        left, top = st.session_state.current_box_position
                        box_size = int(1024 * 0.25)
                        
                        if font:
                            text_bbox = draw.textbbox((0, 0), text_info["text"], font=font)
                            text_width = text_bbox[2] - text_bbox[0]
                            text_height = text_bbox[3] - text_bbox[1]
                        else:
                            text_width = len(text_info["text"]) * text_info["size"] * 0.5
                            text_height = text_info["size"]
                            
                        text_x = left + (box_size - text_width) // 2
                        text_y = top + (box_size - text_height) // 2
                        
                        # 绘制文字
                        draw.text((text_x, text_y), text_info["text"], fill=text_info["color"], font=font)
                        
                        # 更新当前图像
                        st.session_state.current_image = st.session_state.final_design.copy()
                    except Exception as e:
                        st.warning(f"重新应用文字时出错: {e}")
                
                # 重新应用之前的Logo
                if 'applied_logo' in st.session_state and 'selected_preset_logo' in st.session_state:
                    logo_info = st.session_state.applied_logo
                    
                    try:
                        logo_path = st.session_state.selected_preset_logo
                        logo_image = Image.open(logo_path).convert("RGBA")
                        
                        # 调整Logo大小
                        box_size = int(1024 * 0.25)
                        logo_width = int(box_size * logo_info["size"] / 100)
                        logo_height = int(logo_width * logo_image.height / logo_image.width)
                        logo_resized = logo_image.resize((logo_width, logo_height), Image.LANCZOS)
                        
                        # 获取选择框位置
                        left, top = st.session_state.current_box_position
                        
                        # 位置映射
                        position_mapping = {
                            "左上": (left + 10, top + 10),
                            "上中": (left + (box_size - logo_width) // 2, top + 10),
                            "右上": (left + box_size - logo_width - 10, top + 10),
                            "居中": (left + (box_size - logo_width) // 2, top + (box_size - logo_height) // 2),
                            "左下": (left + 10, top + box_size - logo_height - 10),
                            "下中": (left + (box_size - logo_width) // 2, top + box_size - logo_height - 10),
                            "右下": (left + box_size - logo_width - 10, top + box_size - logo_height - 10)
                        }
                        
                        logo_x, logo_y = position_mapping.get(logo_info["position"], (left + 10, top + 10))
                        
                        # 设置透明度
                        if logo_info["opacity"] < 100:
                            logo_data = logo_resized.getdata()
                            new_data = []
                            for item in logo_data:
                                r, g, b, a = item
                                new_a = int(a * logo_info["opacity"] / 100)
                                new_data.append((r, g, b, new_a))
                            logo_resized.putdata(new_data)
                        
                        # 粘贴Logo到设计
                        st.session_state.final_design.paste(logo_resized, (logo_x, logo_y), logo_resized)
                        
                        # 更新当前图像
                        st.session_state.current_image = st.session_state.final_design.copy()
                    except Exception as e:
                        st.warning(f"重新应用Logo时出错: {e}")
                
                # 更新已应用的颜色状态
                st.session_state.current_applied_color = st.session_state.shirt_color_hex
        
        # Display current image and get click coordinates
        st.markdown("### 设计预览")
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
        
        # 显示最终设计结果（如果有）
        if st.session_state.final_design is not None:
            st.markdown("### 最终效果")
            st.image(st.session_state.final_design, use_container_width=True)
            
            # 添加T恤规格信息
            # 显示当前颜色
            color_name = {
                "#FFFFFF": "White",
                "#000000": "Black",
                "#FF0000": "Red",
                "#00FF00": "Green",
                "#0000FF": "Blue",
                "#FFFF00": "Yellow",
                "#FF00FF": "Magenta",
                "#00FFFF": "Cyan",
                "#C0C0C0": "Silver",
                "#808080": "Gray"
            }.get(st.session_state.shirt_color_hex.upper(), "Custom")
            st.markdown(f"**颜色:** {color_name} ({st.session_state.shirt_color_hex})")
            
            # 添加清空设计按钮
            if st.button("🗑️ 清空所有设计", key="clear_designs"):
                # 清空所有设计相关的状态变量
                st.session_state.generated_design = None
                st.session_state.applied_text = None
                st.session_state.applied_logo = None
                # 重置最终设计为基础T恤图像
                st.session_state.final_design = None
                # 重置当前图像为带选择框的基础图像
                temp_image, _ = draw_selection_box(st.session_state.base_image, st.session_state.current_box_position)
                st.session_state.current_image = temp_image
                st.rerun()
            
            # 下载和确认按钮
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                buf = BytesIO()
                st.session_state.final_design.save(buf, format="PNG")
                buf.seek(0)
                st.download_button(
                    label="💾 下载设计",
                    data=buf,
                    file_name="custom_tshirt.png",
                    mime="image/png"
                )
            
            with dl_col2:
                # Confirm completion button
                if st.button("确认完成"):
                    st.session_state.page = "survey"
                    st.rerun()
    
    with controls_col:
        # 操作区，包含AI建议和其他控制选项
        with st.expander("🤖 AI设计建议", expanded=True):
            # 添加用户偏好输入
            user_preference = st.text_input("描述您喜欢的风格或用途", placeholder="例如：运动风格、商务场合、休闲日常等")
            
            col_pref1, col_pref2 = st.columns([1, 1])
            with col_pref1:
                # 添加预设风格选择
                preset_styles = ["", "时尚休闲", "商务正式", "运动风格", "摇滚朋克", "日系动漫", "文艺复古", "美式街头"]
                selected_preset = st.selectbox("或选择预设风格:", preset_styles)
                if selected_preset and not user_preference:
                    user_preference = selected_preset
            
            with col_pref2:
                # 添加获取建议按钮
                if st.button("获取个性化AI建议", key="get_ai_advice"):
                    with st.spinner("正在生成个性化设计建议..."):
                        suggestions = get_ai_design_suggestions(user_preference)
                        st.session_state.ai_suggestions = suggestions
    
    # Return to main interface button - modified here
    if st.button("返回主页"):
        # Clear all design-related states
        st.session_state.base_image = None
        st.session_state.current_image = None
        st.session_state.current_box_position = None
        st.session_state.generated_design = None
        st.session_state.final_design = None
        st.session_state.applied_text = None
        st.session_state.applied_logo = None
        # Only change page state, retain user info and experiment group
        st.session_state.page = "welcome"
        st.rerun() 
