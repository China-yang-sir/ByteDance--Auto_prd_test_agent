import streamlit as st
import base64
import io
import json
import re
import sys
import os

# 确保能引用到 config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.prompts import PromptManager
from openai import OpenAI

def _resolve_qwen_config(api_key=None, model_name=None):
    """统一解析 Qwen 配置，支持显式参数 + 环境变量。"""
    final_api_key = api_key or os.environ.get("QWEN_API_KEY") or os.environ.get("GEMINI_API_KEY")
    final_base_url = os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    final_model = model_name or os.environ.get("QWEN_MODEL_NAME", "qwen-plus")
    return final_api_key, final_base_url, final_model


def _build_client(api_key=None):
    final_api_key, final_base_url, _ = _resolve_qwen_config(api_key=api_key)
    if not final_api_key:
        raise ValueError("缺少 API Key，请配置 QWEN_API_KEY")
    return OpenAI(api_key=final_api_key, base_url=final_base_url)


def _to_data_url_from_pil(img):
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _convert_user_input_to_content(user_input):
    """
    将现有调用链中的 user_input（字符串/列表/图像）转换为 OpenAI 兼容 content。
    兼容旧逻辑：可能传 str，也可能传 [text, PIL.Image, {mime_type,data}]。
    """
    if isinstance(user_input, str):
        return user_input

    if not isinstance(user_input, list):
        return str(user_input)

    content_items = []
    text_fragments = []

    for item in user_input:
        if isinstance(item, str):
            text_fragments.append(item)
            continue

        # PIL Image: 通过 duck typing 判断
        if hasattr(item, "save") and hasattr(item, "mode"):
            data_url = _to_data_url_from_pil(item)
            content_items.append({
                "type": "image_url",
                "image_url": {"url": data_url}
            })
            continue

        # 兼容 PDF 的旧字典结构: {"mime_type":"application/pdf", "data": bytes}
        if isinstance(item, dict) and item.get("mime_type") == "application/pdf":
            # OpenAI-compatible chat 一般不直接接收二进制 PDF，这里给模型一个明确说明，保持流程不断裂。
            text_fragments.append("[系统提示] 检测到 PDF 二进制输入。请基于可见上下文进行概括；若信息不足请明确说明。")
            continue

        text_fragments.append(str(item))

    if text_fragments:
        content_items.insert(0, {"type": "text", "text": "\n".join(text_fragments)})

    if not content_items:
        return ""

    # 仅文本时，直接返回字符串，避免不必要复杂格式
    only_text = all(part.get("type") == "text" for part in content_items)
    if only_text:
        return "\n".join(part.get("text", "") for part in content_items)

    return content_items


def _normalize_history(history):
    """将历史记录规范为 OpenAI 消息格式。"""
    if not history:
        return []

    normalized = []
    for msg in history:
        if isinstance(msg, dict) and msg.get("role") in {"system", "user", "assistant"}:
            normalized.append({"role": msg["role"], "content": msg.get("content", "")})
            continue
        # 兼容不可识别历史对象
        normalized.append({"role": "assistant", "content": str(msg)})
    return normalized

@st.cache_data(ttl=3600)
def get_available_models(api_key):
    """获取可用模型列表：优先读环境变量，否则给出常用 Qwen 兜底。"""
    _, _, default_model = _resolve_qwen_config(api_key=api_key)
    env_models = os.environ.get("QWEN_AVAILABLE_MODELS", "").strip()
    if env_models:
        models = [m.strip() for m in env_models.split(",") if m.strip()]
        return models or [default_model]

    # 对部分兼容端点，models.list 可能不可用，因此这里走稳健兜底
    return [default_model, "qwen-turbo", "qwen-max"]

def extract_json_from_text(text):
    """从 AI 的对话回复中提取 JSON 代码块"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    pattern = r"```(?:json)?\s*(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    
    if matches:
        longest_match = max(matches, key=len)
        try:
            return json.loads(longest_match.strip())
        except json.JSONDecodeError:
            pass
            
    return None

def get_qwen_chat_response(api_key, model_name, history, user_input, system_instruction=None):

    try:
        client = _build_client(api_key)
        _, _, final_model = _resolve_qwen_config(api_key=api_key, model_name=model_name)

        messages = _normalize_history(history)
        if system_instruction:
            messages = [{"role": "system", "content": str(system_instruction)}] + messages

        content = _convert_user_input_to_content(user_input)
        messages.append({"role": "user", "content": content})

        response = client.chat.completions.create(
            model=final_model,
            messages=messages,
        )
        text = (response.choices[0].message.content or "").strip()

        updated_history = _normalize_history(history) + [
            {"role": "user", "content": content},
            {"role": "assistant", "content": text},
        ]
        return text, updated_history
    except Exception as e:
        error_msg = f"模型调用出错: {str(e)}"
        print(error_msg)
        return error_msg, history

def generate_summary(api_key, content, model_name=None):
    try:
        input_str = str(content)[:8000]
        # 使用配置中的 Prompt
        prompt = PromptManager.SUMMARY_PROMPT
        resp_text, _ = get_qwen_chat_response(
            api_key=api_key,
            model_name=model_name,
            history=[],
            user_input=f"{prompt}\n\n{input_str}",
        )
        return resp_text.strip()
    except Exception as e:
        print(f"摘要生成失败: {e}")
        return "未命名业务文档"
    
def get_qwen_embedding(api_key, input_texts, model_name=None):
    """统一 Embedding 调用。"""
    if isinstance(input_texts, str):
        input_texts = [input_texts]

    client = _build_client(api_key)
    _, _, _ = _resolve_qwen_config(api_key=api_key, model_name=model_name)
    embedding_model = os.environ.get("QWEN_EMBEDDING_MODEL", "text-embedding-v3")

    result = client.embeddings.create(model=embedding_model, input=input_texts)
    return [item.embedding for item in result.data]