import streamlit as st
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import cairosvg
from openai import OpenAI
from streamlit_image_coordinates import streamlit_image_coordinates
import os

# API配置信息 - 实际使用时应从主文件传入或使用环境变量
API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
BASE_URL = "https://api.deepbricks.ai/v1/"

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

def apply_color_to_shirt(image, color_hex):
    """给T恤应用新颜色
    
    Args:
        image: 原始T恤图像
        color_hex: 十六进制颜色代码，如 "#FFFFFF"
        
    Returns:
        应用新颜色后的T恤图像
    """
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

# AI Creation Group design page
def show_high_complexity_popup_sales():
    st.title("👕 AI Co-Creation Experiment Platform")
    st.markdown("### High Task Complexity-Pop up Sales - Create Your Unique T-shirt Design")
    
    # 添加Pop-up Sales情境描述
    st.info("""
    **Pop-up Store Environment**
    
    You are visiting our temporary pop-up store in a busy shopping mall. There are other customers 
    waiting for their turn to use this customization kiosk. The store staff has informed you that 
    the experience is limited to 15 minutes per customer. Please design your T-shirt efficiently 
    while enjoying this exclusive in-person customization opportunity.
    """)
    
    # 任务复杂度说明
    st.markdown("""
    <div style="background-color:#f0f0f0; padding:10px; border-radius:5px; margin-bottom:15px">
    <b>Advanced Customization Options</b>: In this experience, you can customize your T-shirt with these extensive options:
    <ul>
        <li>Choose from different collar styles</li>
        <li>Adjust sleeve length and style</li>
        <li>Select fabric types and materials</li>
        <li>Create detailed design patterns</li>
        <li>Position your design precisely on the T-shirt</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # 初始化T恤颜色状态变量
    if 'shirt_color_hex' not in st.session_state:
        st.session_state.shirt_color_hex = "#FFFFFF"  # 默认白色
    if 'original_base_image' not in st.session_state:
        st.session_state.original_base_image = None  # 保存原始白色T恤图像
    
    # Create two-column layout
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("## Design Area")
        
        # 添加AI建议框
        with st.expander("🤖 AI Design Suggestions", expanded=True):
            st.markdown("""
            **Professional Design Guide (Quick Version):**
            
            Light-colored T-shirts work best with dark or colorful patterns, while dark T-shirts pair effectively with bright or metallic effect designs. Center chest position is ideal for logo display, left chest works for small emblems, and the back is suitable for larger patterns. To complete your design within 15 minutes, consider using preset patterns or simple design elements. Ensure visual balance between your pattern and the T-shirt color and style, avoiding overly complex design elements. For time-limited decisions, select one design style and two to three complementary colors. For formal occasions, choose minimalist designs and neutral tones; for casual settings, opt for brighter colors and creative designs.
            """)
        
        # 只在Design Pattern标签页激活时显示点击提示
        if st.session_state.get('active_tab') == "Design Pattern":
            # 删除提示文本
            pass
        
        # 初始化T恤样式状态变量
        if 'collar_style' not in st.session_state:
            st.session_state.collar_style = "Round"
        if 'sleeve_style' not in st.session_state:
            st.session_state.sleeve_style = "Short"
        if 'fabric_type' not in st.session_state:
            st.session_state.fabric_type = "Cotton"
        
        # Load T-shirt base image
        if st.session_state.base_image is None:
            try:
                # 加载原始白色T恤图像
                original_image = Image.open("white_shirt.png").convert("RGBA")
                st.session_state.original_base_image = original_image.copy()
                
                # 应用当前选择的颜色
                colored_image = apply_color_to_shirt(original_image, st.session_state.shirt_color_hex)
                st.session_state.base_image = colored_image
                
                # Initialize by drawing selection box in the center
                initial_image, initial_pos = draw_selection_box(colored_image)
                st.session_state.current_image = initial_image
                st.session_state.current_box_position = initial_pos
            except Exception as e:
                st.error(f"Error loading T-shirt image: {e}")
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
                # 重置状态变量
                st.session_state.generated_design = None
                st.session_state.preset_design = None
                st.session_state.drawn_design = None
                st.session_state.final_design = None
                # 重置当前图像为带选择框的基础图像
                if st.session_state.get('active_tab') == "Design Pattern":
                    temp_image, _ = draw_selection_box(st.session_state.base_image, st.session_state.current_box_position)
                else:
                    temp_image = st.session_state.base_image.copy()
                st.session_state.current_image = temp_image
                st.rerun()
            
            st.image(st.session_state.final_design, use_container_width=True)
            
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
        
        # 创建高级选项卡
        tab1, tab2, tab3 = st.tabs(["T-shirt Style", "Design Pattern", "Text/Logo"])
        
        with tab1:
            st.markdown("### T-shirt Customization")
            
            # 添加衣领风格选择
            collar_options = ["Crew Neck", "V-Neck", "Polo", "Henley", "Scoop Neck"]
            collar_style = st.selectbox("Collar style:", collar_options,
                                       index=collar_options.index(st.session_state.collar_style)
                                       if st.session_state.collar_style in collar_options else 0)
            
            # 添加袖子风格选择
            sleeve_options = ["Short Sleeve", "Long Sleeve", "3/4 Sleeve", "Sleeveless", "Raglan"]
            sleeve_style = st.selectbox("Sleeve style:", sleeve_options,
                                       index=sleeve_options.index(st.session_state.sleeve_style)
                                       if st.session_state.sleeve_style in sleeve_options else 0)
            
            # 面料选择
            fabric_options = ["Cotton", "Polyester", "Cotton-Polyester Blend", "Jersey Knit", "Organic Cotton"]
            fabric_type = st.selectbox("Fabric type:", fabric_options,
                                      index=fabric_options.index(st.session_state.fabric_type)
                                      if st.session_state.fabric_type in fabric_options else 0)
            
            # 添加T恤颜色选择
            st.markdown("### T-shirt Color")
            shirt_color = st.color_picker("Choose your T-shirt color:", st.session_state.shirt_color_hex)
            
            # 如果颜色发生变化，更新T恤颜色
            if shirt_color != st.session_state.shirt_color_hex:
                st.session_state.shirt_color_hex = shirt_color
                
                # 重新着色T恤图像
                if st.session_state.original_base_image is not None:
                    # 对原始白色T恤应用新颜色
                    new_colored_image = apply_color_to_shirt(st.session_state.original_base_image, shirt_color)
                    st.session_state.base_image = new_colored_image
                    
                    # 更新当前图像（带红框的）
                    new_current_image, _ = draw_selection_box(new_colored_image, st.session_state.current_box_position)
                    st.session_state.current_image = new_current_image
                    
                    # 如果有最终设计，也需要更新
                    if st.session_state.final_design is not None:
                        # 重置最终设计，让用户重新应用设计元素
                        st.session_state.final_design = None
                    
                    st.rerun()
            
            # 应用T恤样式按钮
            if st.button("Apply T-shirt Style", key="apply_style"):
                # 更新存储的样式值
                st.session_state.collar_style = collar_style
                st.session_state.sleeve_style = sleeve_style
                st.session_state.fabric_type = fabric_type
                
                # 显示确认信息
                st.success(f"T-shirt style updated: {collar_style} collar, {sleeve_style} sleeves, {fabric_type} fabric")
                
                # 添加倒计时提醒（针对popup环境）
                st.warning("⏱️ Remember: You have 15 minutes to complete your design!")
        
        with tab2:
            # User input for personalization parameters
            theme = st.text_input("Theme or keyword (required)", "Elegant floral pattern")
            
            # Add style selection dropdown with more professional style options
            style_options = [
                "Watercolor style", "Sketch style", "Geometric shapes", "Minimalist", 
                "Vintage style", "Pop art", "Japanese style", "Nordic design",
                "Classical ornament", "Digital illustration", "Abstract art"
            ]
            style = st.selectbox("Design style", style_options, index=0)
            
            # Improved color selection
            color_scheme_options = [
                "Soft warm tones (pink, gold, light orange)",
                "Fresh cool tones (blue, mint, white)",
                "Nature colors (green, brown, beige)",
                "Bright and vibrant (red, yellow, orange)",
                "Elegant deep tones (navy, purple, dark green)",
                "Black and white contrast",
                "Custom colors"
            ]
            color_scheme = st.selectbox("Color scheme", color_scheme_options)
            
            # If custom colors are selected, show input field
            if color_scheme == "Custom colors":
                colors = st.text_input("Enter desired colors (comma separated)", "pink, gold, sky blue")
            else:
                # Set corresponding color values based on selected scheme
                color_mapping = {
                    "Soft warm tones (pink, gold, light orange)": "pink, gold, light orange, cream",
                    "Fresh cool tones (blue, mint, white)": "sky blue, mint green, white, light gray",
                    "Nature colors (green, brown, beige)": "forest green, brown, beige, olive",
                    "Bright and vibrant (red, yellow, orange)": "bright red, yellow, orange, lemon yellow",
                    "Elegant deep tones (navy, purple, dark green)": "navy blue, violet, dark green, burgundy",
                    "Black and white contrast": "black, white, gray"
                }
                colors = color_mapping.get(color_scheme, "blue, green, red")
            
            # 高级设计选项
            st.markdown("### Advanced Design Settings")
            
            # 添加复杂度和详细程度滑块
            complexity = st.slider("Design complexity", 1, 10, 5)
            detail_level = "low" if complexity <= 3 else "medium" if complexity <= 7 else "high"
            
            # 添加特殊效果选项
            effect_options = ["None", "Distressed", "Vintage", "Metallic", "Glitter", "Gradient"]
            special_effect = st.selectbox("Special effect:", effect_options)
            
            # 应用位置和大小设置
            st.markdown("### Position & Scale")
            position_x = st.slider("Horizontal position", -100, 100, 0)
            position_y = st.slider("Vertical position", -100, 100, 0)
            scale = st.slider("Design size", 25, 150, 100, 5, format="%d%%")
            
            # 生成AI设计按钮
            generate_col1, generate_col2 = st.columns(2)
            with generate_col1:
                if st.button("🎨 Generate Design", key="generate_design"):
                    if not theme.strip():
                        st.warning("Please enter at least a theme or keyword!")
                    else:
                        # 构建高级提示文本
                        effect_prompt = "" if special_effect == "None" else f"Apply {special_effect} effect to the design. "
                        
                        prompt_text = (
                            f"Design a T-shirt pattern with '{theme}' theme using {style}. "
                            f"Use the following colors: {colors}. "
                            f"Design complexity is {complexity}/10 with {detail_level} level of detail. "
                            f"{effect_prompt}"
                            f"Create a PNG format image with transparent background, suitable for T-shirt printing."
                        )
                        
                        with st.spinner("🔮 Generating design... please wait"):
                            # 显示倒计时提醒（针对popup环境）
                            st.info("⏱️ Design generation will take about 15-20 seconds")
                            
                            custom_design = generate_vector_image(prompt_text)
                            
                            if custom_design:
                                st.session_state.generated_design = custom_design
                                
                                # Composite on the original image
                                composite_image = st.session_state.base_image.copy()
                                
                                # Place design at current selection position with size and position modifiers
                                left, top = st.session_state.current_box_position
                                box_size = int(1024 * 0.25)
                                
                                # 应用缩放
                                actual_size = int(box_size * scale / 100)
                                
                                # 应用位置偏移
                                max_offset = box_size - actual_size
                                actual_x = int((position_x / 100) * (max_offset / 2))
                                actual_y = int((position_y / 100) * (max_offset / 2))
                                
                                # 最终位置
                                final_left = left + (box_size - actual_size) // 2 + actual_x
                                final_top = top + (box_size - actual_size) // 2 + actual_y
                                
                                # Scale generated pattern to selection area size
                                scaled_design = custom_design.resize((actual_size, actual_size), Image.LANCZOS)
                                
                                try:
                                    # Ensure transparency channel is used for pasting
                                    composite_image.paste(scaled_design, (final_left, final_top), scaled_design)
                                except Exception as e:
                                    st.warning(f"Transparent channel paste failed, direct paste: {e}")
                                    composite_image.paste(scaled_design, (final_left, final_top))
                                
                                st.session_state.final_design = composite_image
                                st.rerun()
                            else:
                                st.error("Failed to generate image, please try again later.")
        
        with tab3:
            # 文字和Logo选项
            st.markdown("### Add Text or Logo")
            
            text_type = st.radio("Select option:", ["Text", "Logo"], horizontal=True)
            
            if text_type == "Text":
                # 文字选项
                text_content = st.text_input("Enter text:", "My Brand")
                
                # 字体选择
                font_options = ["Arial", "Times New Roman", "Courier", "Verdana", "Georgia", "Script", "Impact"]
                font_family = st.selectbox("Font family:", font_options)
                
                # 文字风格
                text_style = st.multiselect("Text style:", ["Bold", "Italic", "Underline", "Shadow", "Outline"], default=["Bold"])
                
                # 文字颜色和大小
                text_color = st.color_picker("Text color:", "#000000")
                text_size = st.slider("Text size:", 20, 120, 48)
                
                # 文字效果
                text_effect = st.selectbox("Text effect:", ["None", "Curved", "Arched", "Wavy", "3D", "Gradient"])
                
                # 对齐方式
                alignment = st.radio("Alignment:", ["Left", "Center", "Right"], horizontal=True, index=1)
                
                # 按钮 - 应用文字
                if st.button("Add Text to Design", key="add_text"):
                    if not text_content.strip():
                        st.warning("Please enter some text!")
                    else:
                        # 创建带有文字的设计
                        if st.session_state.base_image is None:
                            st.warning("Please wait for the T-shirt image to load")
                        else:
                            # 创建新的设计或使用现有最终设计
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
                                "Script": "SCRIPTBL.TTF",
                                "Impact": "impact.ttf"
                            }
                            
                            # 尝试加载选择的字体
                            try:
                                from PIL import ImageFont
                                # 尝试获取选择的字体
                                font_file = font_mapping.get(font_family, "arial.ttf")
                                
                                # 尝试加载字体，如果失败则尝试系统字体路径
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
                                    
                                    for path in system_font_paths:
                                        try:
                                            font = ImageFont.truetype(path + font_file, text_size)
                                            break
                                        except:
                                            continue
                                
                                # 如果没有找到指定字体，尝试使用系统默认字体
                                if font is None:
                                    fallback_fonts = ["DejaVuSans.ttf", "FreeSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf"]
                                    for fallback in fallback_fonts:
                                        for path in system_font_paths:
                                            try:
                                                font = ImageFont.truetype(path + fallback, text_size)
                                                if font:
                                                    break
                                            except:
                                                continue
                                        if font:
                                            break
                                
                                # 如果所有尝试都失败，使用默认字体
                                if font is None:
                                    font = ImageFont.load_default()
                                    st.warning("Could not load selected font. Using default font instead.")
                            except Exception as e:
                                st.warning(f"Font loading error: {e}")
                                font = None
                            
                            # 获取选择框位置
                            left, top = st.session_state.current_box_position
                            box_size = int(1024 * 0.25)
                            
                            # 根据对齐方式计算文字位置
                            text_bbox = draw.textbbox((0, 0), text_content, font=font)
                            text_width = text_bbox[2] - text_bbox[0]
                            text_height = text_bbox[3] - text_bbox[1]
                            
                            if alignment == "Left":
                                text_x = left + 10
                            elif alignment == "Right":
                                text_x = left + box_size - text_width - 10
                            else:  # Center
                                text_x = left + (box_size - text_width) // 2
                            
                            text_y = top + (box_size - text_height) // 2
                            
                            # 绘制文字
                            draw.text((text_x, text_y), text_content, fill=text_color, font=font)
                            
                            # 更新设计
                            st.session_state.final_design = new_design
                            st.rerun()
            else:  # Logo options
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
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error processing logo: {e}")
    
    # Return to main interface button - modified here
    if st.button("Return to Main Page"):
        # Clear all design-related states
        for key in ['base_image', 'current_image', 'current_box_position', 
                   'generated_design', 'final_design', 'preset_design', 
                   'drawn_design', 'design_mode', 'active_tab']:
            if key in st.session_state:
                st.session_state[key] = None
        # 设置默认活动标签页
        st.session_state.active_tab = "T-shirt Style"
        # 设置默认设计模式
        st.session_state.design_mode = "preset"
        # Only change page state, retain user info and experiment group
        st.session_state.page = "welcome"
        st.rerun() 