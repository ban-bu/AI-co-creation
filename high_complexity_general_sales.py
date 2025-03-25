import streamlit as st
from PIL import Image, ImageDraw
import os
import requests
from io import BytesIO
import cairosvg
from openai import OpenAI
from streamlit_image_coordinates import streamlit_image_coordinates
from streamlit_drawable_canvas import st_canvas
import numpy as np
# 导入面料纹理模块
from fabric_texture import apply_fabric_texture

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

# 修改改变T恤颜色的函数，添加纹理支持
def change_shirt_color(image, color_hex, apply_texture=False, fabric_type=None):
    """改变T恤的颜色，可选择应用面料纹理"""
    # 判断是否是应用了纹理的图像，如果是，则重新从原始图像开始处理
    # 这可以确保每次更改颜色时都从原始状态开始，而不是在已应用纹理的图像上再次修改
    if hasattr(st.session_state, 'original_base_image') and st.session_state.original_base_image is not None:
        # 使用原始白色T恤图像作为基础
        image = st.session_state.original_base_image.copy()
    
    # 转换十六进制颜色为RGB
    color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    
    # 创建副本避免修改原图
    colored_image = image.copy().convert("RGBA")
    
    # 获取图像数据
    data = colored_image.getdata()
    
    # 创建新数据
    new_data = []
    # 白色阈值 - 调整这个值可以控制哪些像素被视为白色/浅色并被改变
    white_threshold = 200
    # 黑色边缘阈值 - 用于识别边框和阴影
    dark_threshold = 40  # 更低的值，确保捕捉所有边缘部分
    
    # 首先进行第一次扫描，收集边缘像素
    edge_pixels = set()
    
    # 先扫描一遍找出所有边缘像素位置
    width, height = colored_image.size
    for y in range(height):
        for x in range(width):
            try:
                pixel = colored_image.getpixel((x, y))
                if len(pixel) == 4:  # RGBA
                    r, g, b, a = pixel
                    if a > 0:  # 非透明像素
                        brightness = (r + g + b) / 3
                        # 识别边缘区域
                        if brightness <= dark_threshold:
                            edge_pixels.add((x, y))
            except:
                continue
    
    # 稍微扩展边缘区域，确保完整捕捉
    expanded_edges = set(edge_pixels)
    for x, y in edge_pixels:
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                expanded_edges.add((x+dx, y+dy))
    
    # 第二次扫描，应用颜色变化，但保留边缘
    idx = 0
    for y in range(height):
        for x in range(width):
            try:
                pixel = data[idx]
                idx += 1
                
                # 检查是否是边缘像素
                if (x, y) in expanded_edges:
                    # 保留边缘像素
                    new_data.append(pixel)
                    continue
                
                # 非边缘像素的处理
                if len(pixel) == 4:  # RGBA
                    r, g, b, a = pixel
                    if a > 0:  # 非透明像素
                        brightness = (r + g + b) / 3
                        if brightness > white_threshold:
                            # 高亮区域 - 完全替换颜色
                            new_data.append((color_rgb[0], color_rgb[1], color_rgb[2], a))
                        elif brightness > dark_threshold:
                            # 中间色调区域 - 混合新颜色
                            blend_factor = (brightness - dark_threshold) / (white_threshold - dark_threshold)
                            new_r = int(r * (1 - blend_factor) + color_rgb[0] * blend_factor)
                            new_g = int(g * (1 - blend_factor) + color_rgb[1] * blend_factor)
                            new_b = int(b * (1 - blend_factor) + color_rgb[2] * blend_factor)
                            new_data.append((new_r, new_g, new_b, a))
                        else:
                            # 如果不在扩展边缘中但亮度低，也保留原色
                            new_data.append(pixel)
                    else:
                        # 完全透明的像素保持不变
                        new_data.append(pixel)
                else:  # RGB
                    r, g, b = pixel
                    brightness = (r + g + b) / 3
                    if brightness > white_threshold:
                        # 高亮区域
                        new_data.append(color_rgb)
                    elif brightness > dark_threshold:
                        # 中间色调
                        blend_factor = (brightness - dark_threshold) / (white_threshold - dark_threshold)
                        new_r = int(r * (1 - blend_factor) + color_rgb[0] * blend_factor)
                        new_g = int(g * (1 - blend_factor) + color_rgb[1] * blend_factor)
                        new_b = int(b * (1 - blend_factor) + color_rgb[2] * blend_factor)
                        new_data.append((new_r, new_g, new_b))
        else:
                        # 暗区域
                        new_data.append(pixel)
            except:
                # 如果出错，保留原像素
                if idx < len(data):
                    new_data.append(data[idx-1])
    
    # 更新图像数据
    colored_image.putdata(new_data)
    
    # 如果需要应用纹理
    if apply_texture and fabric_type:
        return apply_fabric_texture(colored_image, fabric_type)
    
    return colored_image

# 复用ai_design_group等文件中的draw_selection_box函数
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

# Preset Design Group design page
def show_high_complexity_general_sales():
    st.title("👕 AI Co-Creation Experiment Platform")
    st.markdown("### High Task Complexity-General Sales - Create Your Unique T-shirt Design")
    
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
    <b>Advanced Customization Options</b>: In this experience, you can customize your T-shirt with these extensive options:
    <ul>
        <li>Select fabric types and materials</li>
        <li>Create detailed design patterns</li>
        <li>Position your design precisely on the T-shirt</li>
        <li>Add text and logo to your design</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # 添加AI建议框
    with st.expander("🤖 AI Design Suggestions", expanded=True):
        st.markdown("""
        **Advanced Personalization Design Guide:**
        
        Consider color psychology when designing your T-shirt - blue conveys professionalism and trust, red expresses passion, while green represents nature and harmony. Choose fabric types based on comfort and durability - cotton fabrics offer softness ideal for everyday wear, while polyester maintains vibrant colors longer. Create visual focus through the rule of thirds and balance your design across the entire T-shirt. Typography serves as a powerful design element, so experiment with various font combinations and text effects for unique visual impact. Ensure your design maintains consistency with your personal or brand identity to enhance recognition. Pay attention to details like text spacing, pattern intricacies, and color transitions to significantly improve design quality. Finally, visualize your design from different angles and distances to ensure clarity and impact in various viewing scenarios.
        """)
    
    # 初始化T恤颜色状态变量 - 固定为白色
    if 'shirt_color_hex' not in st.session_state:
        st.session_state.shirt_color_hex = "#FFFFFF"  # 固定为白色
    if 'original_base_image' not in st.session_state:
        st.session_state.original_base_image = None  # 保存原始白色T恤图像
    if 'fabric_type' not in st.session_state:
        st.session_state.fabric_type = "Cotton"  # 默认面料类型
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "T-shirt & Text/Logo"  # 默认活动标签页
    
    # Create two-column layout
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("## Design Area")
        
        # Load T-shirt base image
        if st.session_state.base_image is None:
            try:
                # 加载原始白色T恤图像
                original_image = Image.open("white_shirt.png").convert("RGBA")
                # 保存原始白色T恤图像 - 这是非常重要的！
                st.session_state.original_base_image = original_image.copy()
                
                # 使用白色T恤并应用当前选择的面料纹理
                colored_image = change_shirt_color(
                    original_image, 
                    "#FFFFFF",  # 固定使用白色
                    apply_texture=True,  # 默认应用纹理
                    fabric_type=st.session_state.fabric_type  # 使用当前选择的面料
                )
                st.session_state.base_image = colored_image
                
                # 设置选择框位置（中心点）
                box_size = int(1024 * 0.25)
                initial_pos = ((colored_image.width - box_size) // 2, (colored_image.height - box_size) // 2)
                st.session_state.current_box_position = initial_pos
                
                # 根据当前活动标签页决定是否显示红框
                if st.session_state.active_tab == "Design Pattern":
                    initial_image, _ = draw_selection_box(colored_image, initial_pos)
                else:
                    initial_image = colored_image.copy()
                
                st.session_state.current_image = initial_image
            except Exception as e:
                st.error(f"Error loading T-shirt image: {e}")
                st.stop()
        
        # 只在Design Pattern标签页激活时显示点击提示
        if st.session_state.get('active_tab') == "Design Pattern":
            st.markdown("**👇 Click anywhere on the T-shirt to position your design**")
        
        # Display current image and get click coordinates
        current_image = st.session_state.current_image
        coordinates = streamlit_image_coordinates(
            current_image,
            key="shirt_image"
        )
        
        # 只在Design Pattern标签页激活时处理点击事件
        if coordinates and st.session_state.get('active_tab') == "Design Pattern":
            # Update selection box at current mouse position
            current_point = (coordinates["x"], coordinates["y"])
            temp_image, new_pos = draw_selection_box(st.session_state.base_image, current_point)
            st.session_state.current_image = temp_image
            st.session_state.current_box_position = new_pos
            st.rerun()

    with col2:
        st.markdown("## Design Parameters")
        
        # 修改选项卡布局：从三个改为两个，将T-shirt Style和Text/Logo合并
        tab1, tab2 = st.tabs(["T-shirt & Text/Logo", "Design Pattern"])
        
        # 创建一个用于切换标签页的radio按钮，但隐藏显示
        active_tab = st.radio(
            "选择标签页",
            ["T-shirt & Text/Logo", "Design Pattern"],
            key="visible_tab", 
            label_visibility="collapsed",
            horizontal=True,
            index=0 if st.session_state.active_tab == "T-shirt & Text/Logo" else 1
        )
        
        # 检测标签页变化
        current_tab = st.session_state.get('active_tab')
        if active_tab != current_tab:
            st.session_state.active_tab = active_tab
            
            # 根据标签页切换更新图像
            if active_tab == "T-shirt & Text/Logo" and st.session_state.base_image is not None:
                # 在T-shirt标签页激活时，更新当前图像为没有红框的版本
                st.session_state.current_image = st.session_state.base_image.copy()
                st.rerun()
            elif active_tab == "Design Pattern" and st.session_state.base_image is not None:
                # 在Design标签页激活时，重新显示红框
                new_image, _ = draw_selection_box(st.session_state.base_image, st.session_state.current_box_position)
                st.session_state.current_image = new_image
                st.rerun()
        
        # 根据当前激活的标签页显示相应内容
        if active_tab == "T-shirt & Text/Logo":
            # T-shirt Customization部分
            st.markdown("### T-shirt Customization")
            
            # 面料选择
            fabric_options = ["Cotton", "Polyester", "Cotton-Polyester Blend", "Jersey", "Linen", "Bamboo"]
            fabric_type = st.selectbox("Fabric type:", fabric_options,
                                      index=fabric_options.index(st.session_state.fabric_type)
                                      if st.session_state.fabric_type in fabric_options else 0)
            
            # 应用T恤样式按钮
            if st.button("Apply Fabric", key="apply_style"):
                # 更新存储的样式值
                old_fabric = st.session_state.fabric_type
                st.session_state.fabric_type = fabric_type
                
                # 无论面料类型是否改变，都应用纹理
                if st.session_state.original_base_image is not None:
                    try:
                        # 应用纹理，使用固定白色
                        new_colored_image = change_shirt_color(
                            st.session_state.original_base_image, 
                            "#FFFFFF",  # 固定使用白色
                            apply_texture=True, 
                            fabric_type=fabric_type
                        )
                    st.session_state.base_image = new_colored_image
                    
                        # 根据当前活动标签页更新图像
                        if st.session_state.active_tab == "Design Pattern":
                            # 在Design Pattern标签页中显示红框
                    new_current_image, _ = draw_selection_box(new_colored_image, st.session_state.current_box_position)
                        else:
                            # 在T-shirt标签页中不显示红框
                            new_current_image = new_colored_image.copy()
                            
                    st.session_state.current_image = new_current_image
                    
                    # 如果有最终设计，也需要更新
                    if st.session_state.final_design is not None:
                        st.session_state.final_design = None
                    
                    st.rerun()
                    except Exception as e:
                        st.warning(f"应用面料纹理时出错: {e}")
                
                # 显示确认信息
                st.success(f"T-shirt fabric updated: {fabric_type}")
            
            # 文字和Logo选项部分
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
        
        elif active_tab == "Design Pattern":
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
    
    # Display final effect - move out of col2, place at bottom of overall page
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
            st.markdown(f"**Fabric:** {st.session_state.fabric_type}")
        
        # Provide download option
        col1, col2 = st.columns(2)
        with col1:
            from io import BytesIO  # 确保BytesIO在此处可用
            buf = BytesIO()
            st.session_state.final_design.save(buf, format="PNG")
            buf.seek(0)
            st.download_button(
                label="💾 Download Custom Design",
                data=buf,
                file_name="custom_tshirt.png",
                mime="image/png"
            )
        
        with col2:
            # Confirm completion button
            if st.button("Confirm Completion"):
                st.session_state.page = "survey"
                st.rerun()

    # Return to main interface button - modified here
    if st.button("Return to Main Page"):
        # Clear all design-related states
        st.session_state.base_image = None
        st.session_state.current_image = None
        st.session_state.current_box_position = None
        st.session_state.generated_design = None
        st.session_state.final_design = None
        st.session_state.original_base_image = None
        # Only change page state, retain user info and experiment group
        st.session_state.page = "welcome"
        st.rerun()

# 添加绘制预览的函数，直接在红框内展示设计
def draw_design_preview(image, design, box_position, design_position, design_scale):
    """在当前图像的红框内直接绘制设计预览"""
    # 创建图像副本
    img_copy = image.copy()
    
    # 获取红框位置和大小
    box_size = int(1024 * 0.25)
    left, top = box_position
    
    # 计算设计的位置和大小
    x_offset, y_offset = design_position
    scale_percent = design_scale
    
    # 计算缩放后的大小
    scaled_size = int(box_size * scale_percent / 100)
    
    # 计算可移动的范围
    max_offset = box_size - scaled_size
    # 将-100到100范围映射到实际的像素偏移
    actual_x_offset = int((x_offset / 100) * (max_offset / 2))
    actual_y_offset = int((y_offset / 100) * (max_offset / 2))
    
    # 计算预览的左上角坐标
    preview_left = left + (box_size - scaled_size) // 2 + actual_x_offset
    preview_top = top + (box_size - scaled_size) // 2 + actual_y_offset
    
    # 确保位置在红框范围内
    preview_left = max(left, min(preview_left, left + box_size - scaled_size))
    preview_top = max(top, min(preview_top, top + box_size - scaled_size))
    
    # 缩放设计图案
    design_scaled = design.resize((scaled_size, scaled_size), Image.LANCZOS)
    
    # 在预览位置粘贴设计图案（显示绿色边框）
    # 创建一个包含设计的新图像，并添加绿色边框
    preview_design = Image.new("RGBA", design_scaled.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(preview_design)
    
    # 创建一个新副本，避免直接修改原图
    design_with_border = design_scaled.copy()
    draw_border = ImageDraw.Draw(design_with_border)
    
    # 绘制绿色边框
    draw_border.rectangle(
        [(0, 0), (scaled_size-1, scaled_size-1)],
        outline=(0, 255, 0),  # 绿色
        width=2
    )
    
    try:
        # 粘贴带边框的设计到主图像
        img_copy.paste(design_with_border, (preview_left, preview_top), design_scaled)
    except Exception as e:
        st.warning(f"Transparent preview paste failed: {e}")
        img_copy.paste(design_with_border, (preview_left, preview_top))
    
    return img_copy

# 修改更新复合图像函数
def update_composite_image(preview_only=False):
    """更新复合图像，显示单种设计（只使用预设设计或绘制设计）"""
    # 创建基础图像的副本
    composite_image = st.session_state.base_image.copy()
    box_size = int(1024 * 0.25)
    left, top = st.session_state.current_box_position
    
    # 根据设计模式决定显示哪种设计
    if st.session_state.design_mode == "preset" and st.session_state.preset_design is not None:
        # 只显示预设设计
        # 获取位置偏移
        x_offset, y_offset = getattr(st.session_state, 'preset_position', (0, 0))
        scale_percent = getattr(st.session_state, 'preset_scale', 40)
        
        # 计算缩放大小 - 相对于选择框的百分比
        scaled_size = int(box_size * scale_percent / 100)
        
        # 根据偏移量计算具体位置
        # 计算可移动的范围，以确保图像不会完全移出框
        max_offset = box_size - scaled_size
        # 将-100到100范围映射到实际的像素偏移
        actual_x_offset = int((x_offset / 100) * (max_offset / 2))
        actual_y_offset = int((y_offset / 100) * (max_offset / 2))
        
        # 最终位置
        paste_x = left + (box_size - scaled_size) // 2 + actual_x_offset
        paste_y = top + (box_size - scaled_size) // 2 + actual_y_offset
        
        # 确保位置在合理范围内
        paste_x = max(left, min(paste_x, left + box_size - scaled_size))
        paste_y = max(top, min(paste_y, top + box_size - scaled_size))
        
        # 缩放预设图案
        preset_scaled = st.session_state.preset_design.resize((scaled_size, scaled_size), Image.LANCZOS)
        
        try:
            # 在计算的位置粘贴图像
            composite_image.paste(preset_scaled, (paste_x, paste_y), preset_scaled)
        except Exception as e:
            st.warning(f"Transparent channel paste failed for preset design: {e}")
            composite_image.paste(preset_scaled, (paste_x, paste_y))
    
    elif st.session_state.design_mode == "draw" and st.session_state.drawn_design is not None:
        # 只显示绘制的设计
        drawn_scaled = st.session_state.drawn_design.resize((box_size, box_size), Image.LANCZOS)
        try:
            composite_image.paste(drawn_scaled, (left, top), drawn_scaled)
        except Exception as e:
            st.warning(f"Transparent channel paste failed for drawn design: {e}")
            composite_image.paste(drawn_scaled, (left, top))
    
    # 如果不是仅预览，则保存最终设计
    if not preview_only:
        st.session_state.final_design = composite_image
    
    return composite_image 

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