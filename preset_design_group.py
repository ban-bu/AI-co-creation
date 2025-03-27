import streamlit as st
from PIL import Image, ImageDraw
import os
from streamlit_image_coordinates import streamlit_image_coordinates
from streamlit_drawable_canvas import st_canvas

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
def show_preset_design_group():
    st.title("👕 Preset Design Experiment Platform")
    st.markdown("### High Task Complexity-General Sales - Choose Your Favorite T-shirt Design")
    
    # 创建两列布局：左侧T恤区域，右侧设计选择区域
    design_area_col, options_col = st.columns([3, 2])
    
    with design_area_col:
        st.markdown("## Design Area")
        
        # Load T-shirt base image
        if st.session_state.base_image is None:
            try:
                base_image = Image.open("white_shirt.png").convert("RGBA")
                st.session_state.base_image = base_image
                # Initialize by drawing selection box in the center
                initial_image, initial_pos = draw_selection_box(base_image)
                st.session_state.current_image = initial_image
                st.session_state.current_box_position = initial_pos
            except Exception as e:
                st.error(f"Error loading white T-shirt image: {e}")
                st.stop()
        
        st.markdown("**👇 Click anywhere on the T-shirt to position your design**")
        
        # 初始化临时设计变量（如果需要）
        if 'temp_preset_design' not in st.session_state:
            st.session_state.temp_preset_design = None
        if 'temp_preset_position' not in st.session_state:
            st.session_state.temp_preset_position = (0, 0)
        if 'temp_preset_scale' not in st.session_state:
            st.session_state.temp_preset_scale = 40
        if 'design_mode' not in st.session_state:
            st.session_state.design_mode = "preset"  # 默认使用预设设计模式
            
        # 准备显示的图像（带有预览效果）
        display_image = st.session_state.current_image.copy()
        
        # 如果有临时预设设计且正在调整位置，直接在红框中显示预览
        if st.session_state.temp_preset_design is not None and st.session_state.design_mode == "preset":
            # 在当前图像上绘制预览
            display_image = draw_design_preview(
                display_image,
                st.session_state.temp_preset_design,
                st.session_state.current_box_position,
                st.session_state.temp_preset_position,
                st.session_state.temp_preset_scale
            )
        
        # Display current image and get click coordinates
        coordinates = streamlit_image_coordinates(
            display_image,
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
            st.markdown("### Final Result")
            
            # 修改清空设计按钮
            if st.button("🗑️ Clear All Designs", key="clear_designs"):
                # 保存当前红框位置
                current_left, current_top = st.session_state.current_box_position
                box_size = int(1024 * 0.25)
                
                # 计算红框中心点坐标
                center_x = current_left + box_size // 2
                center_y = current_top + box_size // 2
                
                # 清空所有设计相关的状态变量
                st.session_state.preset_design = None
                st.session_state.drawn_design = None
                st.session_state.temp_preset_design = None
                st.session_state.preset_position = (0, 0)
                st.session_state.preset_scale = 40
                # 重置最终设计为基础T恤图像
                st.session_state.final_design = None
                
                # 使用中心点坐标重新绘制选择框
                temp_image, new_pos = draw_selection_box(st.session_state.base_image, (center_x, center_y))
                st.session_state.current_image = temp_image
                st.session_state.current_box_position = new_pos
                st.rerun()
            
            st.image(st.session_state.final_design, use_container_width=True)
            
            # Provide download and completion options
            download_col, complete_col = st.columns(2)
            with download_col:
                from io import BytesIO
                buf = BytesIO()
                st.session_state.final_design.save(buf, format="PNG")
                buf.seek(0)
                st.download_button(
                    label="💾 Download Custom Design",
                    data=buf,
                    file_name="custom_tshirt.png",
                    mime="image/png"
                )
            
            with complete_col:
                # Add confirm completion button that navigates to the survey page
                if st.button("Confirm Completion"):
                    st.session_state.page = "survey"
                    st.rerun()

    # 设计选择区域
    with options_col:
        st.markdown("## Design Options")
        
        # 添加设计模式选择
        design_mode = st.radio(
            "Choose design method:",
            options=["Use preset design", "Draw your own design"],
            horizontal=True,
            index=0 if st.session_state.design_mode == "preset" else 1
        )
        
        # 更新设计模式
        if (design_mode == "Use preset design" and st.session_state.design_mode != "preset") or \
           (design_mode == "Draw your own design" and st.session_state.design_mode != "draw"):
            st.session_state.design_mode = "preset" if design_mode == "Use preset design" else "draw"
            st.rerun()
        
        # 根据当前设计模式显示相应的界面
        if st.session_state.design_mode == "preset":
            # 预设设计选择界面
            st.markdown("## Preset Design Selection")
            
            # Get all images from predesign folder
            predesign_folder = "predesign"
            design_files = []
            
            # Ensure folder exists
            if not os.path.exists(predesign_folder):
                st.error(f"Preset design folder not found: {predesign_folder}, please make sure it exists.")
            else:
                # Get all supported image files
                for file in os.listdir(predesign_folder):
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        design_files.append(file)
            
            if not design_files:
                st.warning(f"No image files found in the {predesign_folder} folder.")
            else:
                # Display image selection interface
                selected_file = st.radio(
                    "Select a design:",
                    options=design_files,
                    horizontal=False
                )
                
                st.session_state.selected_preset = selected_file
                
                # Display selected design
                if st.session_state.selected_preset:
                    try:
                        # 加载选定的设计图像
                        design_path = os.path.join(predesign_folder, selected_file)
                        selected_design = Image.open(design_path).convert("RGBA")
                        st.image(selected_design, caption=f"Preset: {selected_file}", use_column_width=True)
                        
                        # 加载到临时设计变量，准备实时预览调整
                        st.session_state.temp_preset_design = selected_design
                        
                        # 调整位置和大小控件
                        st.markdown("### Adjust Position & Size")
                        
                        # 添加缩放滑块
                        scale_percent = st.slider("Size", 10, 100, st.session_state.temp_preset_scale, 5, 
                                                 help="Size of the design")
                        
                        # 设置水平和垂直位置的滑块
                        x_offset = st.slider("Horizontal", -100, 100, st.session_state.temp_preset_position[0], 5, 
                                           help="Move left/right")
                        y_offset = st.slider("Vertical", -100, 100, st.session_state.temp_preset_position[1], 5,
                                           help="Move up/down")
                        
                        # 当控制值改变时更新临时状态
                        if (x_offset, y_offset) != st.session_state.temp_preset_position or scale_percent != st.session_state.temp_preset_scale:
                            st.session_state.temp_preset_position = (x_offset, y_offset)
                            st.session_state.temp_preset_scale = scale_percent
                            st.rerun()  # 触发重新运行以更新预览
                        
                        # 应用设计按钮
                        if st.button("Apply to T-shirt", key="apply_preset"):
                            # 将临时设计和位置应用到实际设计
                            st.session_state.preset_design = st.session_state.temp_preset_design
                            st.session_state.preset_position = st.session_state.temp_preset_position
                            st.session_state.preset_scale = st.session_state.temp_preset_scale
                            
                            # 清除绘制的设计，确保只显示一种设计
                            st.session_state.drawn_design = None
                            
                            # 生成复合图像
                            update_composite_image()
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error processing preset design: {e}")
        else:
            # 绘图设计界面
            st.markdown("## Draw Your Own Design")
            st.markdown("Create your own pattern:")
            
            pen_color = st.color_picker("Pen color", "#000000")
            pen_size = st.slider("Pen thickness", 1, 20, 5)
            
            # Drawing canvas
            canvas_result = st_canvas(
                fill_color="rgba(255, 255, 255, 0.3)",  # Fill color
                stroke_width=pen_size,  # Stroke width
                stroke_color=pen_color,  # Stroke color
                background_color="#ffffff",  # Background color
                height=300,
                width=300,
                drawing_mode="freedraw",  # Drawing mode
                key="canvas",
            )

            # Check if there is a drawing
            if canvas_result.image_data is not None:
                # Button to apply to T-shirt
                if st.button("Apply Drawing to T-shirt", key="apply_drawing"):
                    # Convert numpy array to PIL image
                    import numpy as np
                    drawn_design = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                    
                    # Create a new transparent background image
                    transparent_design = Image.new("RGBA", drawn_design.size, (0, 0, 0, 0))
                    
                    # Process image, making white background transparent
                    width, height = drawn_design.size
                    for x in range(width):
                        for y in range(height):
                            r, g, b, a = drawn_design.getpixel((x, y))
                            # If pixel is close to white, set it to fully transparent
                            if r > 240 and g > 240 and b > 240:
                                transparent_design.putpixel((x, y), (0, 0, 0, 0))
                            else:
                                # Otherwise keep original color and opacity
                                transparent_design.putpixel((x, y), (r, g, b, 255))
                    
                    # 存储绘制的设计到专用状态变量
                    st.session_state.drawn_design = transparent_design
                    
                    # 清除预设设计，确保只显示一种设计
                    st.session_state.preset_design = None
                    st.session_state.preset_position = (0, 0)
                    st.session_state.preset_scale = 40
                    
                    # 生成复合图像
                    update_composite_image()
                    st.rerun()
                
                if st.button("Clear Canvas", key="clear_canvas"):
                    # 不做任何操作，因为canvas会在页面刷新时自动清空
                    st.rerun()

    # 添加分隔线
    st.markdown("---")
    
    # Return to main interface button - 现在放在页面底部
    if st.button("Return to Main Page", key="return_to_main_page"):
        # Clear all design-related states
        st.session_state.base_image = None
        st.session_state.current_image = None
        st.session_state.current_box_position = None
        st.session_state.generated_design = None
        st.session_state.preset_design = None
        st.session_state.drawn_design = None
        st.session_state.final_design = None
        st.session_state.selected_preset = None
        st.session_state.temp_preset_design = None
        st.session_state.design_mode = "preset"  # 重置设计模式为默认值
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