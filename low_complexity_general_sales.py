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
                {"role": "system", "content": """你是一位专业的T恤设计顾问。请针对用户提供的关键词或主题，提供5种不同的设计方案建议，包括图案描述、配色方案、风格特点等。
                
                必须严格按以下JSON格式输出：
                {
                  "designs": [
                    {
                      "theme": "主题名称",
                      "style": "设计风格",
                      "colors": "主要颜色组合",
                      "description": "详细描述"
                    },
                    ... 更多设计方案 ...
                  ]
                }
                
                确保每个设计方案都是独特的、有创意的，并且适合T恤印刷。描述要简洁明了但富有表现力。
                """},
                {"role": "user", "content": f"请为'{prompt}'这个设计理念提供5种T恤图案设计方案。"}
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
                            "style": "现代简约",
                            "colors": "黑白灰",
                            "description": "无法获取AI设计建议，提供了一个默认设计方案。"
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
                        "style": "现代简约",
                        "colors": "黑白灰",
                        "description": "基于您的关键词生成的简约风格设计。"
                    }
                ]
            }
    except Exception as e:
        st.error(f"Error calling ChatGPT API: {e}")
        return {
            "designs": [
                {
                    "theme": "错误恢复设计",
                    "style": "简约",
                    "colors": "黑白",
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
                <h4 style="color:#4B0082;">Let AI help you create design combinations</h4>
                <p>Enter a theme or concept, and our AI will generate multiple design ideas including styles, colors, and descriptions.</p>
                </div>
                """, unsafe_allow_html=True)
                
                # 用户输入设计关键词或主题
                design_idea = st.text_input("Enter your design concept or theme:", 
                                           placeholder="For example: summer beach, cyberpunk, abstract art, etc.")
                
                # AI设计建议按钮
                if st.button("🎨 Get AI Design Suggestions", key="get_ai_suggestions"):
                    if not design_idea.strip():
                        st.warning("Please enter a design concept or theme!")
                    else:
                        with st.spinner("AI is generating design combinations..."):
                            # 调用AI生成设计建议
                            suggestions = get_ai_design_suggestions(design_idea)
                            
                            if suggestions and "designs" in suggestions:
                                # 保存建议到session state
                                st.session_state.design_suggestions = suggestions["designs"]
                                
                                # 强制页面刷新，以确保建议正确显示
                                st.rerun()
                            else:
                                st.error("Failed to generate design suggestions. Please try again.")
                
                # 如果已有设计建议，显示它们
                if st.session_state.design_suggestions:
                    st.markdown("### AI Generated Design Suggestions")
                    
                    # 使用列布局美化展示
                    suggestions_cols = st.columns(2)  # 2列显示，每列最多显示3个设计
                    
                    for i, design in enumerate(st.session_state.design_suggestions):
                        with suggestions_cols[i % 2]:  # 交替放置在两列中
                            with st.container():
                                # 为每个设计建议创建彩色卡片效果
                                st.markdown(f"""
                                <div style="border:1px solid #ddd; padding:15px; margin:8px 0; border-radius:10px; 
                                     background-color:rgba(240,248,255,0.6); box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
                                <h4 style="color:#1E90FF; margin-top:0;">Design {i+1}: {design.get('theme', 'Custom Design')}</h4>
                                <p><strong>Style:</strong> {design.get('style', 'N/A')}</p>
                                <p><strong>Colors:</strong> <span style="color:#4B0082;">{design.get('colors', 'N/A')}</span></p>
                                <p style="font-style:italic;">{design.get('description', '')}</p>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # 将此设计用作提示词的按钮 - 更美观的按钮样式
                                if st.button(f"✨ Use Design {i+1}", key=f"use_design_{i}"):
                                    # 构建完整的设计提示词
                                    prompt = f"{design.get('theme')} in {design.get('style')} style with {design.get('colors')} colors. {design.get('description')}"
                                    # 设置到设计提示输入框
                                    st.session_state.selected_prompt = prompt
                                    st.rerun()
            
            # 设计生成主题 - 如果有AI建议选择的提示词，则使用它
            theme = st.text_input("Design prompt (describe your design idea)", 
                             value=st.session_state.get("selected_prompt", "Elegant minimalist pattern in blue and white colors"))
            
            # 如果存在选择的提示词，添加提示
            if st.session_state.selected_prompt:
                st.info("👆 Using AI suggested design prompt. You can modify it or enter your own.")
            
            # 生成AI设计按钮
            if st.button("🎨 Generate Design", key="generate_design_button"):
                if not theme.strip():
                    st.warning("Please enter a design prompt!")
                else:
                    # 创建进度显示区
                    progress_container = st.empty()
                    progress_container.info("🔍 Analyzing your design prompt...")
                    
                    # 检查是否使用AI建议的设计方案
                    is_ai_suggested = st.session_state.selected_prompt and theme == st.session_state.selected_prompt
                    
                    # 构建更丰富的提示文本
                    if is_ai_suggested:
                        # 如果是AI建议的设计，使用更具体的提示词
                        # 从选定的设计方案中提取关键信息
                        for design in st.session_state.design_suggestions:
                            if f"{design.get('theme')} in {design.get('style')} style with {design.get('colors')} colors. {design.get('description')}" == theme:
                                # 使用更具体的设计指南增强提示词
                                prompt_text = (
                                    f"Create a T-shirt design with theme: {design.get('theme')}. "
                                    f"Use {design.get('style')} style with these colors: {design.get('colors')}. "
                                    f"Design details: {design.get('description')}. "
                                    f"Create a high-quality PNG image with transparent background, suitable for T-shirt printing. "
                                    f"The design should be clean, modern and visually appealing."
                                )
                                break
                        else:
                            # 如果没有找到匹配项，使用原始主题
                            prompt_text = theme
                        
                        progress_container.info("🎭 Using AI suggested design concept...")
                    else:
                        # 用户自定义提示词，增强提示内容
                        prompt_text = (
                            f"Design a pattern with the following description: {theme}. "
                            f"Create a PNG format image with transparent background, suitable for printing. "
                            f"Make the design visually appealing and modern."
                        )
                        progress_container.info("🖌️ Preparing your custom design concept...")
                    
                    # 更新进度
                    time.sleep(0.5)  # 短暂延迟以使UI反应更自然
                    progress_container.info("🧠 Generating unique design based on your prompt...")
                    
                    # 调用AI生成图像
                    custom_design = generate_vector_image(prompt_text)
                    
                    if custom_design:
                        # 更新进度
                        progress_container.info("✨ Design created! Applying to your T-shirt...")
                        time.sleep(0.5)  # 短暂延迟
                        
                        st.session_state.generated_design = custom_design
                        
                        # Composite on the original image
                        composite_image = st.session_state.base_image.copy()
                        
                        # Place design at current selection position
                        left, top = st.session_state.current_box_position
                        box_size = int(1024 * 0.25)
                        
                        # Scale generated pattern to selection area size
                        scaled_design = custom_design.resize((box_size, box_size), Image.LANCZOS)
                        
                        try:
                            # Ensure transparency channel is used for pasting
                            composite_image.paste(scaled_design, (left, top), scaled_design)
                        except Exception as e:
                            st.warning(f"Transparent channel paste failed, direct paste: {e}")
                            composite_image.paste(scaled_design, (left, top))
                        
                        # 保存最终设计但不立即刷新页面
                        st.session_state.final_design = composite_image
                        
                        # 同时更新current_image以便在T恤图像上直接显示设计
                        st.session_state.current_image = composite_image.copy()
                        
                        # 清除进度消息并显示成功消息
                        progress_container.success("🎉 Design successfully applied to your T-shirt!")
                        
                        # 添加一些关于设计的反馈
                        st.markdown(f"""
                        <div style="background-color:#f0f8ff; padding:10px; border-radius:5px; margin:10px 0;">
                        <h4>Design Details:</h4>
                        <p>✅ Applied design based on: "{theme}"</p>
                        <p>✅ Positioned at your selected location</p>
                        <p>✅ Ready for customization or download</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 强制页面刷新以显示结果
                        st.rerun()
                    else:
                        # 清除进度消息并显示错误
                        progress_container.error("❌ Could not generate the design. Please try a different prompt or try again later.")
        
        with tab2:
            # 添加文字/Logo选项
            st.write("Add text or logo to your design:")
            
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
