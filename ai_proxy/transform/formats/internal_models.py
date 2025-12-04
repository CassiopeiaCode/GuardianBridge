"""
内部统一数据模型 - 支持工具调用
"""
from typing import List, Optional, Literal, Any
from pydantic import BaseModel


class InternalTool(BaseModel):
    """工具定义"""
    name: str
    description: Optional[str] = None
    input_schema: dict  # JSON Schema 格式


class InternalToolCall(BaseModel):
    """工具调用"""
    id: str
    name: str
    arguments: dict


class InternalToolResult(BaseModel):
    """工具结果"""
    call_id: str
    name: Optional[str] = None
    output: Any


class InternalImageBlock(BaseModel):
    """图片内容块"""
    url: str
    detail: Optional[str] = None


class InternalContentBlock(BaseModel):
    """内容块 - 支持文本、工具调用、工具结果"""
    type: Literal["text", "tool_call", "tool_result", "image_url"]
    text: Optional[str] = None
    tool_call: Optional[InternalToolCall] = None
    tool_result: Optional[InternalToolResult] = None
    image_url: Optional[InternalImageBlock] = None


class InternalMessage(BaseModel):
    """统一消息格式"""
    role: Literal["system", "user", "assistant", "tool"]
    content: List[InternalContentBlock]


class InternalChatRequest(BaseModel):
    """统一聊天请求格式"""
    messages: List[InternalMessage]
    model: str
    stream: bool = False
    tools: List[InternalTool] = []
    tool_choice: Optional[Any] = None  # 直接透传，如 "auto" / { "type": "function", ... }
    extra: dict = {}


class InternalChatResponse(BaseModel):
    """统一聊天响应格式"""
    id: str
    model: str
    messages: List[InternalMessage]  # 支持多轮，包含工具调用
    finish_reason: Optional[str] = None
    usage: Optional[dict] = None
    extra: dict = {}


class InternalStreamChunk(BaseModel):
    """统一流式响应块"""
    delta: str = ""  # 文本增量
    tool_calls_delta: Optional[List[dict]] = None  # 工具调用增量
    is_final: bool = False
    extra: dict = {}
