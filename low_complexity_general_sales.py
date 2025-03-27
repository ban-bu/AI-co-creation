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
        "position": "Center"  # 默认中心位置
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
    # 初始化AI设计建议相关变量    
    if 'design_suggestions' not in st.session_state:
        st.session_state.design_suggestions = []  # 存储AI生成的设计建议
    if 'selected_prompt' not in st.session_state:
        st.session_state.selected_prompt = ""  # 存储用户选择的设计提示词
    
    # Create two-column layout
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("## Design Area")
        
        # 添加AI建议框
        with st.expander("🤖 AI Design Suggestions", expanded=True):
            st.markdown("""
            **Personalization Design Guide:**
            
            Consider selecting colors that complement your personal style and wardrobe preferences for maximum versatility. Light-colored T-shirts work best with darker design patterns, while dark T-shirts create striking contrast with lighter patterns or text. Experiment with positioning your design in different locations on the T-shirt to find the optimal visual impact - centered designs offer classic appeal while offset designs can create interesting visual dynamics. Minimalist designs tend to be more versatile and suitable for various occasions, allowing your T-shirt to transition seamlessly between casual and semi-formal settings. When adding text, choose legible fonts at appropriate sizes to ensure your message remains clear and impactful regardless of viewing distance.
            """)
    
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
            
        # 将Final Result部分移到左侧栏中
        if st.session_state.final_design is not None:
            st.markdown("### Final Result")
            
            # 添加清空设计按钮
            if st.button("🗑️ Clear All Designs", key="clear_designs"):
                # 清空所有设计相关的状态变量
                st.session_state.generated_design = None
                # 重置最终设计为基础T恤图像
                st.session_state.final_design = None
                # 重置当前图像为带选择框的基础图像
                temp_image, _ = draw_selection_box(st.session_state.base_image, st.session_state.current_box_position)
                st.session_state.current_image = temp_image
                st.rerun()
            
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
            st.markdown(f"**Color:** {color_name} ({st.session_state.shirt_color_hex})")
            
            # Provide download option
            col1a, col1b = st.columns(2)
            with col1a:
                buf = BytesIO()
                st.session_state.final_design.save(buf, format="PNG")
                buf.seek(0)
                st.download_button(
                    label="💾 Download Custom Design",
                    data=buf,
                    file_name="custom_tshirt.png",
                    mime="image/png"
                )
            
            with col1b:
                # Confirm completion button
                if st.button("Confirm Completion"):
                    st.session_state.page = "survey"
                    st.rerun()

    with col2:
        st.markdown("## Design Parameters")
        
        # Simplified design option tabs
        tab1, tab2 = st.tabs(["Generate Design", "Add Text/Logo"])
        
        with tab1:
            st.markdown("### Design Options")
            
            # 添加设计提示说明
            st.markdown("""
            <div style="background-color:#f0f0f0; padding:10px; border-radius:5px; margin-bottom:15px">
            <b>Design Prompt Guide</b>: 描述您想要的T恤设计，包括：
            <ul>
                <li>T恤颜色（如：白色、黑色、红色等）</li>
                <li>文字内容（在引号内指定，如："Hello World"）</li>
                <li>Logo位置（如：中心、左上、右下等）</li>
                <li>是否需要Logo（提及"logo"或"图标"）</li>
            </ul>
            例如："白色T恤，中心位置添加logo，文字是'Summer Vibes'"
            </div>
            """, unsafe_allow_html=True)
            
            # 添加颜色选择器
            shirt_color = st.color_picker("T-shirt color:", st.session_state.shirt_color_hex)
            
            # 如果颜色发生变化，更新T恤颜色
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
                    
                    st.rerun()
            
            # 添加AI辅助设计功能
            with st.expander("🤖 AI Design Assistant", expanded=True):
                st.markdown("""
                <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:15px">
                <h4 style="color:#4B0082;">让AI帮你设计T恤</h4>
                <p>输入一个主题或概念，AI将为您生成多种T恤设计方案，包括颜色、文字和位置建议。</p>
                <div style="background-color:#fff; padding:8px; border-radius:5px; margin-top:10px; border:1px dashed #ccc;">
                <strong>示例主题：</strong> 夏日海滩、网络朋克、复古风、极简主义、运动风、环保主题、城市景观、音乐节
                </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 用户输入设计关键词或主题
                design_idea = st.text_input("输入您的设计概念或主题:", 
                                           placeholder="例如：夏日海滩、网络朋克、抽象艺术等")
                
                # AI设计建议按钮
                if st.button("🎨 获取AI设计建议", key="get_ai_suggestions"):
                    if not design_idea.strip():
                        st.warning("请输入设计概念或主题!")
                    else:
                        with st.spinner("AI正在生成设计方案..."):
                            # 调用AI生成设计建议
                            suggestions = get_ai_design_suggestions(design_idea)
                            
                            if suggestions and "designs" in suggestions:
                                # 保存建议到session state
                                st.session_state.design_suggestions = suggestions["designs"]
                                
                                # 强制页面刷新，以确保建议正确显示
                                st.rerun()
                            else:
                                st.error("无法生成设计建议。请稍后再试。")
                
                # 如果已有设计建议，显示它们
                if st.session_state.design_suggestions:
                    st.markdown("### AI生成的设计建议")
                    
                    # 使用列布局美化展示
                    suggestions_cols = st.columns(2)  # 2列显示，每列最多显示3个设计
                    
                    for i, design in enumerate(st.session_state.design_suggestions):
                        with suggestions_cols[i % 2]:  # 交替放置在两列中
                            with st.container():
                                # 为每个设计建议创建彩色卡片效果
                                # 获取颜色对应的十六进制值用于显示
                                color_name = design.get('color', 'white').lower()
                                color_hex = {
                                    "white": "#FFFFFF", "black": "#000000", "red": "#FF0000",
                                    "blue": "#0000FF", "green": "#00FF00", "yellow": "#FFFF00",
                                    "purple": "#800080", "pink": "#FFC0CB", "gray": "#808080",
                                    "cyan": "#00FFFF"
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
                                    <strong>颜色:</strong> {design.get('color', 'N/A')}
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
                                
                                # 将此设计用作提示词的按钮 - 更美观的按钮样式
                                if st.button(f"✨ 使用设计 {i+1}", key=f"use_design_{i}"):
                                    # 构建完整的设计提示词
                                    prompt = f"{design.get('color', '白色')}T恤，{design.get('position', 'Center')}位置添加\"{design.get('text', 'My Brand')}\"文字"
                                    if design.get('needs_logo', False):
                                        prompt += "，需要添加logo"
                                    # 设置到设计提示输入框
                                    st.session_state.selected_prompt = prompt
                                    st.rerun()
            
            # 设计提示输入
            design_prompt = st.text_input(
                "Design prompt (描述您想要的T恤设计):",
                value=st.session_state.get("selected_prompt", "白色T恤，中心位置添加'My Brand'文字"),
                help="描述您想要的T恤设计，包括颜色、文字、logo等元素"
            )
            
            # 添加设计提示示例
            st.markdown("""
            <div style="background-color:#f0f0f0; padding:8px; border-radius:5px; margin:5px 0 15px 0; font-size:0.9em;">
            <strong>设计提示示例:</strong>
            <ul style="margin-top:5px; margin-bottom:5px;">
              <li>黑色T恤，中心位置添加"CODER"文字</li>
              <li>蓝色T恤，左上角添加logo，底部添加"Ocean"文字</li>
              <li>红色T恤，右上位置添加"2024"文字</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
            
            # 如果存在选择的提示词，添加提示
            if st.session_state.selected_prompt:
                st.info("👆 Using AI suggested design prompt. You can modify it or enter your own.")
            
            # 解析设计提示按钮
            if st.button("✨ Apply Design", key="parse_design_button"):
                if not design_prompt.strip():
                    st.warning("Please enter a design prompt!")
                else:
                    # 创建进度显示区
                    progress_container = st.empty()
                    progress_container.info("🔍 Analyzing your design prompt...")
                    
                    # 解析设计提示
                    design_info = parse_design_prompt(design_prompt)
                    
                    # 应用T恤颜色
                    if design_info["color"] != st.session_state.shirt_color_hex:
                        st.session_state.shirt_color_hex = design_info["color"]
                        if st.session_state.original_base_image is not None:
                            # 更新T恤颜色
                            progress_container.info("🎨 Applying T-shirt color...")
                            new_colored_image = change_shirt_color(st.session_state.original_base_image, design_info["color"])
                            st.session_state.base_image = new_colored_image
                            
                            # 更新当前图像
                            new_current_image, _ = draw_selection_box(new_colored_image, st.session_state.current_box_position)
                            st.session_state.current_image = new_current_image
                    
                    # 创建设计复合图像
                    composite_image = st.session_state.base_image.copy()
                    
                    # 如果有文字内容，添加到设计中
                    if design_info["text"]:
                        progress_container.info("✍️ Adding text to design...")
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
                            text_bbox = draw.textbbox((0, 0), design_info["text"], font=font)
                            text_width = text_bbox[2] - text_bbox[0]
                            text_height = text_bbox[3] - text_bbox[1]
                            
                            # 根据position确定文字位置
                            if design_info["position"] == "Center":
                                text_x = left + (box_size - text_width) // 2
                                text_y = top + (box_size - text_height) // 2
                            elif design_info["position"] == "Top Left":
                                text_x = left + 10
                                text_y = top + 10
                            elif design_info["position"] == "Top Right":
                                text_x = left + box_size - text_width - 10
                                text_y = top + 10
                            elif design_info["position"] == "Bottom Left":
                                text_x = left + 10
                                text_y = top + box_size - text_height - 10
                            elif design_info["position"] == "Bottom Right":
                                text_x = left + box_size - text_width - 10
                                text_y = top + box_size - text_height - 10
                            elif design_info["position"] == "Top Center":
                                text_x = left + (box_size - text_width) // 2
                                text_y = top + 10
                            else:  # "Bottom Center"
                                text_x = left + (box_size - text_width) // 2
                                text_y = top + box_size - text_height - 10
                            
                            # 绘制文字
                            draw.text((text_x, text_y), design_info["text"], fill="#000000", font=font)
                        except Exception as e:
                            st.warning(f"Error adding text: {e}")
                    
                    # 如果需要logo，添加提示
                    if design_info.get("needs_logo", False):
                        progress_container.info("🔄 Logo suggested - please select a logo in the 'Add Text/Logo' tab")
                        
                        # 可以考虑自动切换到Logo选项卡
                        st.session_state.auto_switch_to_logo = True
                    
                    # 更新设计
                    st.session_state.final_design = composite_image
                    
                    # 同时更新current_image以便在T恤图像上直接显示设计
                    st.session_state.current_image = composite_image.copy()
                    
                    # 清除进度消息并显示成功消息
                    progress_container.success("🎉 Design successfully applied to your T-shirt!")
                    
                    # 添加设计详情反馈
                    st.markdown(f"""
                    <div style="background-color:#f0f8ff; padding:10px; border-radius:5px; margin:10px 0;">
                    <h4>Applied Design Details:</h4>
                    <p>✅ T-shirt color: {design_info['color']}</p>
                    <p>✅ Text content: {design_info['text'] if design_info['text'] else 'None'}</p>
                    <p>✅ Position: {design_info['position']}</p>
                    <p>{"✅ Logo suggestion detected - please add a logo in the next tab" if design_info.get("needs_logo", False) else "❌ No logo requested"}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 如果应该自动切换到Logo选项卡
                    if design_info.get("needs_logo", False) and st.session_state.get("auto_switch_to_logo", False):
                        st.info("💡 Tip: Switch to the 'Add Text/Logo' tab to add your logo")
                    
                    # 重新加载页面以显示变化
                    st.rerun()
        
        with tab2:
            # 将标题改为更清晰的描述
            st.markdown("### Add Additional Elements")
            st.write("Add text or logo to further customize your T-shirt:")
            
            # 选择文字或Logo
            text_or_logo = st.radio("Select option:", ["Text", "Logo"], horizontal=True)
            
            if text_or_logo == "Text":
                # 文字选项
                text_content = st.text_input("Enter text to add:", "My Brand")
                
                # 添加字体选择
                font_options = ["Arial", "Times New Roman", "Courier", "Verdana", "Georgia", "Impact"]
                font_family = st.selectbox("Font family:", font_options)
                
                # 文字样式
                text_style = st.multiselect("Text style:", ["Bold", "Italic"], default=[])
                
                # 文字颜色
                text_color = st.color_picker("Text color:", "#000000")
                
                # 增大默认文字大小范围
                text_size = st.slider("Text size:", 20, 120, 48)
                
                # 添加文字按钮
                if st.button("Add Text to Design"):
                    if not text_content.strip():
                        st.warning("Please enter some text!")
                    else:
                        # 创建带有文字的设计
                        if st.session_state.base_image is None:
                            st.warning("Please wait for the T-shirt image to load")
                        else:
                            # 创建一个新的设计或使用现有最终设计
                            if st.session_state.final_design is not None:
                                new_design = st.session_state.final_design.copy()
                            else:
                                new_design = st.session_state.base_image.copy()
                            
                            # 准备绘图对象
                            draw = ImageDraw.Draw(new_design)
                            
                            # 字体映射
                            font_mapping = {
                                "Arial": "arial.ttf",
                                "Times New Roman": "times.ttf",
                                "Courier": "cour.ttf",
                                "Verdana": "verdana.ttf",
                                "Georgia": "georgia.ttf",
                                "Impact": "impact.ttf"
                            }
                            
                            # 通用字体备选方案
                            fallback_fonts = ["DejaVuSans.ttf", "FreeSans.ttf", "LiberationSans-Regular.ttf"]
                            
                            # 导入字体，尝试获取选择的字体
                            font = None
                            try:
                                from PIL import ImageFont
                                # 尝试获取选择的字体
                                font_file = font_mapping.get(font_family, "arial.ttf")
                                
                                # 尝试加载字体，如果失败则尝试备选字体
                                try:
                                    font = ImageFont.truetype(font_file, text_size)
                                except:
                                    # 尝试系统字体路径
                                    system_font_paths = [
                                        "/Library/Fonts/",  # macOS
                                        "/System/Library/Fonts/",  # macOS系统
                                        "C:/Windows/Fonts/",  # Windows
                                        "/usr/share/fonts/truetype/",  # Linux
                                    ]
                                    
                                    # 尝试所有可能的字体位置
                                    for path in system_font_paths:
                                        try:
                                            font = ImageFont.truetype(path + font_file, text_size)
                                            break
                                        except:
                                            continue
                                    
                                    # 如果仍然失败，尝试备选字体
                                    if font is None:
                                        for fallback in fallback_fonts:
                                            try:
                                                for path in system_font_paths:
                                                    try:
                                                        font = ImageFont.truetype(path + fallback, text_size)
                                                        break
                                                    except:
                                                        continue
                                                if font:
                                                    break
                                            except:
                                                continue
                                
                                # 如果所有尝试都失败，使用默认字体
                                if font is None:
                                    font = ImageFont.load_default()
                                    # 尝试将默认字体放大到指定大小
                                    default_size = 10  # 假设默认字体大小
                                    scale_factor = text_size / default_size
                                    # 注意：这种方法可能不是最佳方案，但可以在没有字体的情况下提供备选
                            except Exception as e:
                                st.warning(f"Font loading error: {e}")
                                font = None
                            
                            # 获取当前选择框位置
                            left, top = st.session_state.current_box_position
                            box_size = int(1024 * 0.25)
                            
                            # 在选择框中居中绘制文字
                            text_bbox = draw.textbbox((0, 0), text_content, font=font)
                            text_width = text_bbox[2] - text_bbox[0]
                            text_height = text_bbox[3] - text_bbox[1]
                            
                            text_x = left + (box_size - text_width) // 2
                            text_y = top + (box_size - text_height) // 2
                            
                            # 绘制文字，使用抗锯齿渲染
                            draw.text((text_x, text_y), text_content, fill=text_color, font=font)
                            
                            # 更新设计
                            st.session_state.final_design = new_design
                            
                            # 同时更新current_image以保持两个显示区域的一致性
                            st.session_state.current_image = new_design.copy()
                            
                            # 强制页面刷新以显示最新结果
                            st.rerun()
            else:  # Logo选项
                # Logo来源选择
                logo_source = st.radio("Logo source:", ["Upload your logo", "Choose from presets"], horizontal=True)
                
                if logo_source == "Upload your logo":
                    # Logo上传选项
                    uploaded_logo = st.file_uploader("Upload your logo (PNG or JPG file):", type=["png", "jpg", "jpeg"])
                    logo_image = None
                    
                    if uploaded_logo is not None:
                        try:
                            logo_image = Image.open(BytesIO(uploaded_logo.getvalue())).convert("RGBA")
                        except Exception as e:
                            st.error(f"Error loading uploaded logo: {e}")
                else:  # Choose from presets
                    # 获取预设logo
                    preset_logos = get_preset_logos()
                    
                    if not preset_logos:
                        st.warning("No preset logos found. Please add some images to the 'logos' folder.")
                        logo_image = None
                    else:
                        # 显示预设logo选择
                        logo_cols = st.columns(min(3, len(preset_logos)))
                        selected_preset_logo = None
                        
                        for i, logo_path in enumerate(preset_logos):
                            with logo_cols[i % 3]:
                                logo_name = os.path.basename(logo_path)
                                try:
                                    logo_preview = Image.open(logo_path).convert("RGBA")
                                    # 调整预览大小
                                    preview_width = 100
                                    preview_height = int(preview_width * logo_preview.height / logo_preview.width)
                                    preview = logo_preview.resize((preview_width, preview_height))
                                    
                                    st.image(preview, caption=logo_name)
                                    if st.button(f"Select {logo_name}", key=f"logo_{i}"):
                                        selected_preset_logo = logo_path
                                except Exception as e:
                                    st.error(f"Error loading logo {logo_name}: {e}")
                        
                        # 如果选择了预设logo
                        logo_image = None
                        if selected_preset_logo:
                            try:
                                logo_image = Image.open(selected_preset_logo).convert("RGBA")
                                st.success(f"Selected logo: {os.path.basename(selected_preset_logo)}")
                            except Exception as e:
                                st.error(f"Error loading selected logo: {e}")
                
                # Logo大小和位置
                logo_size = st.slider("Logo size:", 10, 100, 40, format="%d%%")
                logo_position = st.radio("Position:", ["Top Left", "Top Center", "Top Right", "Center", "Bottom Left", "Bottom Center", "Bottom Right"], index=3)
                
                # Logo透明度
                logo_opacity = st.slider("Logo opacity:", 10, 100, 100, 5, format="%d%%")
                
                # 应用Logo按钮
                if st.button("Apply Logo", key="apply_logo"):
                    if logo_image is None:
                        if logo_source == "Upload your logo":
                            st.warning("Please upload a logo first!")
                        else:
                            st.warning("Please select a preset logo first!")
                    else:
                        # 处理Logo
                        try:
                            # 调整Logo大小
                            box_size = int(1024 * 0.25)
                            logo_width = int(box_size * logo_size / 100)
                            logo_height = int(logo_width * logo_image.height / logo_image.width)
                            logo_resized = logo_image.resize((logo_width, logo_height), Image.LANCZOS)
                            
                            # 创建新的设计或使用现有最终设计
                            if st.session_state.final_design is not None:
                                new_design = st.session_state.final_design.copy()
                            else:
                                new_design = st.session_state.base_image.copy()
                            
                            # 获取选择框位置
                            left, top = st.session_state.current_box_position
                            
                            # 计算Logo位置
                            if logo_position == "Top Left":
                                logo_x, logo_y = left + 10, top + 10
                            elif logo_position == "Top Center":
                                logo_x, logo_y = left + (box_size - logo_width) // 2, top + 10
                            elif logo_position == "Top Right":
                                logo_x, logo_y = left + box_size - logo_width - 10, top + 10
                            elif logo_position == "Center":
                                logo_x, logo_y = left + (box_size - logo_width) // 2, top + (box_size - logo_height) // 2
                            elif logo_position == "Bottom Left":
                                logo_x, logo_y = left + 10, top + box_size - logo_height - 10
                            elif logo_position == "Bottom Center":
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
                            try:
                                new_design.paste(logo_resized, (logo_x, logo_y), logo_resized)
                            except Exception as e:
                                st.warning(f"Logo paste failed: {e}")
                            
                            # 更新设计
                            st.session_state.final_design = new_design
                            
                            # 同时更新current_image以保持两个显示区域的一致性
                            st.session_state.current_image = new_design.copy()
                            
                            # 强制页面刷新以显示最新结果
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error processing logo: {e}")
    
    # 删除原来页面底部的Final Result部分
    # Return to main interface button - modified here
    if st.button("Return to Main Page"):
        # Clear all design-related states
        st.session_state.base_image = None
        st.session_state.current_image = None
        st.session_state.current_box_position = None
        st.session_state.generated_design = None
        st.session_state.final_design = None
        # Only change page state, retain user info and experiment group
        st.session_state.page = "welcome"
        st.rerun() 
