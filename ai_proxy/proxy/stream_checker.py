"""
流式响应检查工具
用于在发送响应头之前检查流式内容是否有效（避免返回空回复）
"""
import json
from typing import Tuple, List, Optional

class StreamChecker:
    """流式内容检查器"""
    
    def __init__(self, format_name: str):
        self.format_name = format_name
        self.accumulated_content = ""
        self.has_tool_call = False
        self.char_threshold = 2
        
    def check_chunk(self, chunk: bytes) -> bool:
        """
        检查 chunk 数据
        Returns:
            bool: 是否已满足放行条件（内容>2chars 或 有工具调用）
        """
        if self.has_tool_call or len(self.accumulated_content) > self.char_threshold:
            return True
            
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            # 忽略解码错误的块（可能是被截断的多字节字符）
            return False
            
        # 简单的 SSE 解析
        for line in text.split('\n'):
            line = line.strip()
            if not line.startswith('data: '):
                continue
                
            data_str = line[6:]  # remove 'data: '
            if data_str == '[DONE]':
                continue
                
            try:
                data = json.loads(data_str)
                self._parse_data(data)
                
                if self.has_tool_call or len(self.accumulated_content) > self.char_threshold:
                    return True
            except json.JSONDecodeError:
                continue
                
        return False

    def _parse_data(self, data: dict):
        """解析单条数据"""
        # OpenAI Chat 格式
        if "choices" in data and isinstance(data["choices"], list):
            for choice in data["choices"]:
                delta = choice.get("delta", {})
                
                # 检查内容
                content = delta.get("content")
                if content:
                    self.accumulated_content += content
                
                # 检查工具调用
                if delta.get("tool_calls"):
                    self.has_tool_call = True
                    
        # Claude 格式 (假设通过 upstream 已经是转为兼容格式，或者透传)
        # 如果是透传的 Claude 原生 SSE，它是 event: ... data: ...
        # 这里简化处理，尝试识别常见的 type
        if "type" in data:
            dtype = data["type"]
            if dtype == "content_block_delta":
                delta = data.get("delta", {})
                if delta.get("type") == "text_delta":
                    self.accumulated_content += delta.get("text", "")
            elif dtype == "message_start":
                # 检查 message 中的 content 是否有 tool_use
                msg = data.get("message", {})
                for c in msg.get("content", []):
                    if c.get("type") == "tool_use":
                        self.has_tool_call = True
            elif dtype == "content_block_start":
                 if data.get("content_block", {}).get("type") == "tool_use":
                     self.has_tool_call = True
