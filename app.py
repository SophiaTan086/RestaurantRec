import math
import gradio as gr
import pandas as pd
import random
from recommender import RestaurantRecommender

recommender = RestaurantRecommender()

# SVG图谱生成
def generate_native_graph_html(selected_name):
    # edge_data 结构：(起点, 终点, 连线描述, 真实留评)
    edge_data = recommender.fetch_graph_data_by_rest(selected_name)
    if len(edge_data) == 0:
        return f"<div style='text-align:center;padding:60px;color:#f97316;font-size:15px;'>💡 {selected_name} 暂无可用关联图谱数据，请尝试在第二页切换其他热门商户。</div>"

    center_node = selected_name
    user_nodes = set()
    cat_nodes = set()
    user_scores = {}    
    user_comments = {}  

    for s, t, lbl, cmt in edge_data:
        if "打分" in lbl:
            user_node = s if t == center_node else t
            user_nodes.add(user_node)
            user_scores[user_node] = lbl
            
            # 重安全清洗过滤，防止破坏前端 JS 语法
            clean_cmt = str(cmt)
            clean_cmt = clean_cmt.replace("\\", "\\\\")  
            clean_cmt = clean_cmt.replace("'", "\\'")    
            clean_cmt = clean_cmt.replace('"', '\\"')    
            clean_cmt = clean_cmt.replace("\n", " ")     
            clean_cmt = clean_cmt.replace("\r", " ")     
            clean_cmt = clean_cmt.strip()
            
            user_comments[user_node] = clean_cmt
        else:
            cat_node = s if t == center_node else t
            if cat_node != center_node:
                cat_nodes.add(cat_node)

    pos = {}
    center_x, center_y = 600, 300
    pos[center_node] = (center_x, center_y)

    # 左侧菜系排布
    cats_list = list(cat_nodes)
    for i, n in enumerate(cats_list):
        radius = 280 if i % 2 == 0 else 380
        angle = 3.14 * (0.6 + (i / max(1, len(cats_list)-1)) * 0.8) 
        pos[n] = (center_x + radius * math.cos(angle), center_y + 220 * math.sin(angle))

    # 右侧用户排布
    users_list = list(user_nodes)
    for i, n in enumerate(users_list):
        track = i % 3
        radius = 320 + track * 85
        angle = 3.14 * (-0.4 + (i / max(1, len(users_list)-1)) * 0.8)
        pos[n] = (center_x + radius * math.cos(angle), center_y + 240 * math.sin(angle))

    svg_elements = []

    # 绘制关系线
    for s, t, lbl, cmt in edge_data:
        if s not in pos or t not in pos:
            continue
        x1, y1 = pos[s]
        x2, y2 = pos[t]
        
        if "打分" in lbl:
            line_color = "#22c55e"
            svg_elements.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{line_color}" stroke-width="1.5" stroke-dasharray="3,3" opacity="0.6"/>')
            mx, my = x1 * 0.7 + x2 * 0.3, y1 * 0.7 + y2 * 0.3
            svg_elements.append(f'<text x="{mx}" y="{my-2}" text-anchor="middle" font-size="8" font-weight="bold" fill="#16a34a" opacity="0.8">{lbl}</text>')
        else:
            line_color = "#0ea5e9"
            svg_elements.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{line_color}" stroke-width="1.5" stroke-dasharray="4,4"/>')
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            svg_elements.append(f'<text x="{mx}" y="{my-4}" text-anchor="middle" font-size="9" fill="#2563eb">{lbl}</text>')

    # 绘制左侧分类（蓝色）
    for n in cats_list:
        x, y = pos[n]
        svg_elements.append(f'''
        <g transform="translate({x},{y})">
            <circle r="15" fill="#0ea5e9" stroke="#fff" stroke-width="2"/>
            <text y="25" text-anchor="middle" font-size="11" font-weight="bold" fill="#334155">{n}</text>
        </g>''')

    # 绘制右侧用户（绿色）
    for n in users_list:
        x, y = pos[n]
        display_name = f"用户_{str(n)[-4:]}" if len(str(n)) > 4 else f"用户_{n}"
        score_text = user_scores.get(n, "暂无分数")
        real_comment = user_comments.get(n, "未填写文字评价")
        
        svg_elements.append(f'''
        <g transform="translate({x},{y})" style="cursor:pointer;" onclick="alert('💬 数据库真实吃货评价\\n━━━━━━━━━━━━━━━\\n👤 用户标识: {n}\\n📊 评分轨迹: {score_text}\\n📝 真实评语: {real_comment}')">
            <circle r="13" fill="#22c55e" stroke="#fff" stroke-width="2" style="filter: drop-shadow(0px 1px 3px rgba(0,0,0,0.15));"/>
            <text y="22" text-anchor="middle" font-size="10" font-weight="500" fill="#475569">{display_name}</text>
        </g>''')

    # 绘制中心餐馆（橙色）
    cx, cy = pos[center_node]
    svg_elements.append(f'''
    <g transform="translate({cx},{cy})">
        <circle r="24" fill="#ff7849" stroke="#fff" stroke-width="3" style="filter: drop-shadow(0px 3px 6px rgba(0,0,0,0.25));"/>
        <text y="36" text-anchor="middle" font-size="13" font-weight="bold" fill="#0f172a">{center_node}</text>
    </g>''')

    all_svg = "\n".join(svg_elements)
    
    html_str = f"""
    <div style="width:98%;background:#f8fafc;border:2px solid #ff7849;border-radius:12px;padding:15px;">
        <div style="color:#334155;margin-bottom:10px;font-size:13px;font-weight:bold;line-height:1.6;">
            🎯 智能图谱交互看板 | 当前主餐馆：<span style="color:#ff7849; font-size:15px;">{selected_name}</span><br>
            <span style="color:#ff7849;">● 橙色大圆</span> = 核心餐厅 &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color:#0ea5e9;">● 左侧蓝色</span> = 菜系标签 &nbsp;&nbsp;|&nbsp;&nbsp;
            <span style="color:#22c55e;">● 右侧绿色</span> = 打卡用户 <span style="color:#16a34a;background:#dcfce7;padding:2px 6px;border-radius:4px;font-size:11px;">💡 点击可穿透调取后台真实评论文本</span>
        </div>
        <svg viewBox="0 0 1200 600" width="100%" height="550" style="background:#ffffff;border-radius:8px;box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);">
            {all_svg}
        </svg>
    </div>"""
    return html_str

# 搜索回调
def search_func(key):
    df = pd.DataFrame(recommender.search_nodes(key))
    if df.empty:
        return pd.DataFrame(columns=["餐厅名", "地址", "评分", "所属菜系"])
    return df

# 推荐回调
def rec_func(rest_name, opt):
    df = pd.DataFrame(recommender.recommend_by_rules(rest_name, opt))
    if df.empty:
        return pd.DataFrame([{"提示说明": "暂无匹配数据", "状态": "当前餐厅与其他实体在该推荐维度下无交叉打卡行为。"}])
    return df

custom_css = """
#table-container .prose { margin-bottom: 0px !important; }
#table-container .prose h3 { margin-bottom: 2px !important; padding-bottom: 0px !important; }
#table-container .gradio-dataframe { margin-top: 0px !important; }
"""

# 页面搭建
with gr.Blocks(theme=gr.themes.Default(primary_hue="orange"), title="餐饮智能推荐系统") as demo:
    gr.Markdown("# 🍔 城市餐饮推荐与知识图谱分析系统")
    rest_list = recommender.get_all_restaurants()
    default_rest = rest_list[0] if len(rest_list) > 0 else ""
    save_select = gr.State(default_rest)

    # Tab1 搜索
    with gr.Tab("🔍 餐饮知识检索"):
        gr.Markdown("### 💡 使用说明：输入关键词（如 Coffee、Pizza、Bar），系统将进行多维度深度匹配，自动推荐评分前20的餐厅。")
        with gr.Row():
            inp_search = gr.Textbox(label="输入关键词：", placeholder="请输入想要检索的菜系标签或特定商户名...")
            btn_search = gr.Button("开始检索", variant="primary")
        out_search = gr.DataFrame(interactive=False)
        btn_search.click(search_func, inputs=[inp_search], outputs=[out_search])

    # Tab2 推荐
    with gr.Tab("🎯 智能推荐引擎"):
        gr.Markdown("### 💡 使用说明：先选择【餐厅】，再选择【推荐策略】，系统将展示过滤后的结果。")
        with gr.Row():
            with gr.Column(scale=1):
                drop_rest = gr.Dropdown(choices=rest_list, value=default_rest, label="📍 选择锚点餐厅")
                radio_opt = gr.Radio(["同菜系推荐", "喜欢这家的人还喜欢", "距离优先推荐"], value="同菜系推荐", label="⚙️ 推荐策略")
                btn_rec = gr.Button("🚀 运行推荐引擎", variant="primary")
                drop_rest.change(lambda x: x, inputs=drop_rest, outputs=save_select)
            with gr.Column(scale=2,elem_id="table-container"):
                gr.Markdown("### 📋 智能推荐结果")
                out_rec = gr.DataFrame(interactive=False)
        btn_rec.click(rec_func, inputs=[drop_rest, radio_opt], outputs=[out_rec])

    # Tab3 图谱
    with gr.Tab("📊 图谱全景动态展示"):
        gr.Markdown("### 💡 使用说明：在第二个页面选项卡（智能推荐引擎）中选择你的目标餐厅，然后点击下方按钮，系统将自动以该餐厅为核心，生成二度关联子图谱。")
        btn_graph = gr.Button("🔄 载入/刷新图谱网络", variant="secondary")
        html_box = gr.HTML("<div style='padding:100px;text-align:center;color:#94a3b8;font-size:14px;'>请先在第二页选好餐厅，再点击上方按钮</div>")
        btn_graph.click(generate_native_graph_html, inputs=save_select, outputs=html_box)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)