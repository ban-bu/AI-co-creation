import streamlit as st
from PIL import Image
from io import BytesIO

# 添加try-except处理cairosvg导入
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

# 将SVG转换为PNG的函数，确保透明度保留
def convert_svg_to_png(svg_content):
    """
    将SVG内容转换为PNG，保留透明背景
    
    参数:
    svg_content - SVG的二进制内容
    
    返回:
    PIL图像对象（RGBA模式）
    """
    if CAIROSVG_AVAILABLE:
        try:
            # 使用cairosvg处理SVG，确保透明度保留
            png_data = cairosvg.svg2png(bytestring=svg_content, background_color=None)
            return Image.open(BytesIO(png_data)).convert("RGBA")
        except Exception as conv_err:
            st.error(f"使用cairosvg处理SVG时出错: {conv_err}")
            
            # 如果cairosvg处理失败，尝试使用svglib
            if SVGLIB_AVAILABLE:
                try:
                    svg_data = BytesIO(svg_content)
                    drawing = svg2rlg(svg_data)
                    png_data = BytesIO()
                    renderPM.drawToFile(drawing, png_data, fmt="PNG")
                    png_data.seek(0)
                    return Image.open(png_data).convert("RGBA")
                except Exception as svg_err:
                    st.error(f"使用svglib处理SVG时出错: {svg_err}")
                    return None
    elif SVGLIB_AVAILABLE:
        # 直接使用svglib作为备选方案
        try:
            svg_data = BytesIO(svg_content)
            drawing = svg2rlg(svg_data)
            png_data = BytesIO()
            renderPM.drawToFile(drawing, png_data, fmt="PNG")
            png_data.seek(0)
            return Image.open(png_data).convert("RGBA")
        except Exception as svg_err:
            st.error(f"使用svglib处理SVG时出错: {svg_err}")
            return None
    else:
        st.error("无法处理SVG格式，SVG处理库未安装")
        return None 