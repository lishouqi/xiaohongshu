import asyncio
import tempfile
import streamlit as st
from constant import DEFAULT_DESCRIPTION, BASIC_CONFIG_DICT
from doc_client import DocGeneratorClient, GenerationConfig
from datetime import datetime
import re

st.set_page_config(
    page_title="📄 批量文档生成器",
    page_icon="📄",
    layout="wide"
)

with st.sidebar:
    st.title("⚙️ 配置")
    basic_tab, api_tab = st.tabs(["基础配置", "API配置"])
    with basic_tab:
        template = st.text_area(
            "📝 提示词模板",
            value=DEFAULT_DESCRIPTION,
            help="使用占位符定义提示词模板",
            height=400
        )
        config_items = list(dict.fromkeys(re.findall(r"\{\%(.+?)\%\}", template, re.DOTALL)))
        default_config_dict = {}
        if config_items:
            default_tab_names = [x for x in config_items if x in BASIC_CONFIG_DICT]
            if default_tab_names:
                default_tabs = st.tabs(default_tab_names)
                for tab, config_name in zip(default_tabs, default_tab_names):
                    with tab:
                        selected_value = st.selectbox(
                            f"请在这里配置你的 :blue[**{config_name}**]",
                            options=["自定义"] + BASIC_CONFIG_DICT[config_name],
                            index=0,
                        )
                        if selected_value is not None:
                            default_config_dict[config_name] = selected_value

        # st.write(default_config_dict)

        st.markdown("- 普通配置参考 :blue[**{%人设%}**]: 包含最长输入500字符,\n\n "
                    "- 长文本配置参考 :red[**{%范文_%}**]: 包含最长输入5000字符，\n\n 📕 请注意，长上下文会消耗更多token，生成速度和稳定性也会下降。")
    base_url = "https://api.302.ai/v1/chat/completions"
    api_key = "sk-HO9SNsAsEer6fjGbWwxGh3KS14bvoy5CfUc4bfjmcnru4IKt"
# with api_tab:
#     base_url = st.text_input("🔗 请输入API地址", value="https://api.302.ai/v1/chat/completions")
#     api_key = st.text_input("🔑 请输入API密钥", type="password", value="sk-HO9SNsAsEer6fjGbWwxGh3KS14bvoy5CfUc4bfjmcnru4IKt")


# 主界面
st.title("📄 小红书文案生成器")
st.markdown("---")


if api_key and base_url:
    client = DocGeneratorClient(api_key=api_key, base_url=base_url)
    if not st.session_state.get("available_models"):    
        try:
            st.session_state["available_models"] = asyncio.run(client.list_available_models())
        except Exception as e:
            st.error(f"获取可用模型列表失败: {str(e)}")
            st.session_state["available_models"] = ["gpt-3.5-turbo", "gpt-4"]
    available_models = st.session_state["available_models"]
    model = st.selectbox(
        "🤖 选择模型",
        options=available_models if available_models else ["gpt-3.5-turbo", "gpt-4"],
        help="选择要使用的OpenAI模型"
    )
    config = GenerationConfig(
        model=model,
        base_url=base_url if base_url else None
    )
    client.config = config

    config_inputs = {}
    if config_items:
        tab_names = [item for item in config_items if (default_config_dict.get(item, None) in ["自定义", None])]
        config_tabs = st.tabs(tab_names)

        for tab, config_name in zip(config_tabs, tab_names):
            is_long_text = "_" in config_name
            with tab:
                config_inputs[config_name] = st.text_area(
                    f"请在这里配置你的 :blue[**{config_name}**]",
                    value="", 
                    key=f"config_{config_name}", 
                    height=300 if is_long_text else 100,
                    max_chars=5000 if is_long_text else 500
                )
        
        for k, v in config_inputs.items():
            template = template.replace(f'{{%{k}%}}', v)
        
        for k, v in default_config_dict.items():
            if v != '自定义':
                template = template.replace(f'{{%{k}%}}', v)

    col3, col4 = st.columns([1, 1])
    with col3:
        num_docs = st.number_input(
            "📄 生成数量",
            min_value=1,
            max_value=100,
            value=5,
            help="选择要生成的文档数量（最多100个）"
        )

    with col4:
        max_concurrent = st.number_input(
            "⚙️ 最大并发数",
            min_value=1,
            max_value=20,
            value=10,
            help="同时生成的文档数量（最多20个），缓慢卡顿时，请勿超过10"
        )

    preview_button = st.button("👁️ 预览", use_container_width=True)

    if preview_button:
        if not api_key:
            st.error("请先输入OpenAI API密钥！")
        else:
            try:
                preview_result = asyncio.run(client.generate_documents(
                    message=template,
                    num_docs=1
                ))[0]
                
                st.markdown("### 👁️ 预览结果")
                st.text_area(
                    label="预览文档内容",
                    value=preview_result,
                    height=200,
                    disabled=True,
                    label_visibility="collapsed"
                )
            except Exception as e:
                print(e)
                st.error(f"预览过程中出现错误: {str(e)}")

    generate_button = st.button("🚀 开始生成", use_container_width=True, disabled=not template.strip())

    if generate_button:
        if not api_key:
            st.error("请先输入OpenAI API密钥！")
        if not template.strip():
            st.error("请先输入你的提示词模板！")
        else:
            progress_container = st.container()
            try:
                with progress_container:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    st.session_state["results"] = asyncio.run(client.generate_documents(
                        message=template,
                        num_docs=num_docs,
                        progress_callback=lambda p: progress_bar.progress(p),
                        status_callback=lambda s: status_text.text(s)
                    ))
                    with tempfile.NamedTemporaryFile(suffix=".xlsx") as temp_file:
                        client.save_documents_excel(st.session_state["results"], temp_file.name)
                        with open(temp_file.name, 'rb') as f:
                            st.session_state["excel_data"] = f.read()
            except Exception as e:
                st.error(f"生成过程中出现错误: {str(e)}")

if "results" in st.session_state:
    with st.container():
        st.markdown("### 📑 生成结果")
        preview_count = min(len(st.session_state["results"]), 10)
        if len(st.session_state["results"]) > 10:
            st.info(f"为了更好的显示效果，仅预览前 {preview_count} 篇文档。您可以使用下方的下载按钮获取所有文档。")
        
        tabs = st.tabs([f"文档 {i+1}" for i in range(preview_count)])
        for i, (tab, doc) in enumerate(zip(tabs, st.session_state["results"][:preview_count])):
            with tab:
                st.text_area(
                    label=f"文档内容 {i+1}",
                    value=doc,
                    height=200,
                    disabled=True,
                    key=f"doc_{i}",
                    label_visibility="collapsed"
                )
        
        st.markdown(f"""
        #### 📊 生成统计
        - 总共生成文档数：{len(st.session_state["results"])}
        - 预览文档数：{preview_count}
        - 单批次并发数：{max_concurrent}
        """)
        
        st.session_state["file_name"] = st.text_input("📝 请输入待保存文件名",
                                value=st.session_state.get("file_name", f"生成结果{datetime.now().strftime('%Y%m%d%H%M%S')}"),
                                max_chars=40)
        if st.session_state.get("file_name", None):
            excel_name = f"{st.session_state['file_name']}.xlsx"
            # For Excel file name
            st.download_button(
                label=f"📊 下载Excel文档 ({len(st.session_state["results"])}篇)",
                data=st.session_state["excel_data"],
                file_name=excel_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            

            text_filename = f"{st.session_state['file_name']}.txt"
            st.download_button(
                label=f"📝 下载文本文档 ({len(st.session_state["results"])}篇)",
                data="\n\n===== 文档分隔线 =====\n\n".join(st.session_state["results"]),
                file_name=text_filename,
                mime="text/plain",
                use_container_width=True
            )
        else:
            st.error("请先输入待保存文件名！")
                        

    # 底部信息
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center'>
            <p>📌 提示：生成大量文档可能需要一些时间，请耐心等待</p>
        </div>
        """,
        unsafe_allow_html=True
    ) 
