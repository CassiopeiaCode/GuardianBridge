"""
Claude Code (Agent SDK) 格式转换
Claude Code 使用不同于 HTTP API 的 Agent SDK 格式
"""
from typing import Dict, Any
from ai_proxy.transform.formats.internal_models import (
    InternalChatRequest,
    InternalChatResponse,
    InternalMessage,
    InternalContentBlock,
    InternalTool,
    InternalToolCall,
    InternalToolResult
)


def can_parse_claude_code(path: str, headers: Dict[str, str], body: Dict[str, Any]) -> bool:
    """判断是否为 Claude Code 格式"""
    # 排斥 Claude Chat 格式：如果路径包含 /messages 或有 anthropic-version header，则不是 Claude Code
    if "/messages" in path or "anthropic-version" in headers:
        return False
    
    # Claude Code SDK 格式特征：
    # 1. 包含 prompt 字段（而不是 messages）
    # 2. 可能包含 options 字段
    # 3. 通常用于本地 Agent SDK 调用，不太可能通过 HTTP
    if "prompt" in body and "messages" not in body:
        # 进一步检查是否有 options 字段
        if "options" in body:
            return True
        # 或者 prompt 是字符串类型（区别于其他格式）
        if isinstance(body.get("prompt"), str):
            return True
    return False


def from_claude_code(body: Dict[str, Any]) -> InternalChatRequest:
    """
    Claude Code 格式 -> 内部格式
    
    Claude Code 格式示例:
    {
        "prompt": "Analyze this code",
        "options": {
            "model": "claude-sonnet-4-5",
            "workingDirectory": "/path",
            "mcpServers": {...},
            "tools": [...],
            "systemPrompt": "..."
        }
    }
    """
    prompt = body.get("prompt", "")
    options = body.get("options", {})
    
    # 提取 system prompt
    messages = []
    system_prompt = options.get("systemPrompt")
    if system_prompt:
        messages.append(InternalMessage(
            role="system",
            content=[InternalContentBlock(type="text", text=system_prompt)]
        ))
    
    # 将 prompt 转换为 user 消息
    # prompt 可能是字符串或生成器
    if isinstance(prompt, str):
        messages.append(InternalMessage(
            role="user",
            content=[InternalContentBlock(type="text", text=prompt)]
        ))
    else:
        # 如果是生成器或其他类型，尝试转字符串
        messages.append(InternalMessage(
            role="user",
            content=[InternalContentBlock(type="text", text=str(prompt))]
        ))
    
    # 解析工具定义（如果有 MCP servers）
    tools = []
    mcp_servers = options.get("mcpServers", {})
    for server_name, server_config in mcp_servers.items():
        # MCP server 可能包含多个工具
        server_tools = server_config.get("tools", [])
        for tool_def in server_tools:
            tools.append(InternalTool(
                name=f"mcp__{server_name}__{tool_def.get('name', '')}",
                description=tool_def.get("description"),
                input_schema=tool_def.get("input_schema", {})
            ))
    
    # 提取其他配置
    model = options.get("model", "claude-sonnet-4-5")
    
    return InternalChatRequest(
        messages=messages,
        model=model,
        stream=False,  # Claude Code SDK 使用异步迭代器，不是标准 stream
        tools=tools,
        tool_choice=options.get("tool_choice"),
        extra={
            "workingDirectory": options.get("workingDirectory"),
            "permissionMode": options.get("permissionMode"),
            "settingSources": options.get("settingSources"),
            "maxBudgetUsd": options.get("maxBudgetUsd"),
            **{k: v for k, v in options.items() 
               if k not in ["model", "systemPrompt", "mcpServers", "workingDirectory", 
                           "permissionMode", "settingSources", "maxBudgetUsd", "tool_choice"]}
        }
    )


def to_claude_code(req: InternalChatRequest) -> Dict[str, Any]:
    """
    内部格式 -> Claude Code 格式
    注意：这个转换可能不完整，因为 Claude Code 是 SDK 格式，不是标准 HTTP API
    """
    # 提取 system 和 user 消息
    system_msgs = [m for m in req.messages if m.role == "system"]
    user_msgs = [m for m in req.messages if m.role == "user"]
    
    # 合并 system prompts
    system_prompt = None
    if system_msgs:
        texts = []
        for m in system_msgs:
            texts.extend([b.text for b in m.content if b.type == "text" and b.text])
        if texts:
            system_prompt = "\n".join(texts)
    
    # 合并 user prompts
    prompt = ""
    if user_msgs:
        texts = []
        for m in user_msgs:
            texts.extend([b.text for b in m.content if b.type == "text" and b.text])
        if texts:
            prompt = "\n".join(texts)
    
    # 构建 options
    options = {
        "model": req.model
    }
    
    if system_prompt:
        options["systemPrompt"] = system_prompt
    
    # 添加额外配置
    if req.extra:
        options.update(req.extra)
    
    # 处理工具（转换为 MCP server 格式）
    if req.tools:
        # 简化处理：将所有工具放入一个默认 MCP server
        options["mcpServers"] = {
            "default": {
                "tools": [
                    {
                        "name": t.name.replace("mcp__default__", ""),
                        "description": t.description,
                        "input_schema": t.input_schema
                    }
                    for t in req.tools
                ]
            }
        }
    
    return {
        "prompt": prompt,
        "options": options
    }


def claude_code_resp_to_internal(resp: Dict[str, Any]) -> InternalChatResponse:
    """
    Claude Code 响应 -> 内部格式
    
    Claude Code 响应是流式消息，包含不同类型：
    - assistant: 助手回复
    - tool_call: 工具调用
    - tool_result: 工具结果
    - system: 系统消息
    - error: 错误
    """
    blocks = []
    message_type = resp.get("type", "")
    
    if message_type == "assistant":
        # 助手消息
        content = resp.get("content", "")
        if isinstance(content, str):
            blocks.append(InternalContentBlock(type="text", text=content))
        elif isinstance(content, list):
            for block in content:
                if block.get("type") == "text":
                    blocks.append(InternalContentBlock(type="text", text=block.get("text", "")))
                elif block.get("type") == "tool_use":
                    blocks.append(InternalContentBlock(
                        type="tool_call",
                        tool_call=InternalToolCall(
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                            arguments=block.get("input", {})
                        )
                    ))
    
    elif message_type == "tool_call":
        # 工具调用消息
        blocks.append(InternalContentBlock(
            type="tool_call",
            tool_call=InternalToolCall(
                id=resp.get("id", ""),
                name=resp.get("tool_name", ""),
                arguments=resp.get("input", {})
            )
        ))
    
    elif message_type == "tool_result":
        # 工具结果消息
        blocks.append(InternalContentBlock(
            type="tool_result",
            tool_result=InternalToolResult(
                call_id=resp.get("tool_call_id", ""),
                name=resp.get("tool_name"),
                output=resp.get("result", "")
            )
        ))
    
    if not blocks:
        blocks.append(InternalContentBlock(type="text", text=""))
    
    return InternalChatResponse(
        id=resp.get("id", resp.get("session_id", "")),
        model=resp.get("model", ""),
        messages=[InternalMessage(role="assistant", content=blocks)],
        finish_reason=resp.get("stop_reason"),
        usage=resp.get("usage"),
        extra={k: v for k, v in resp.items() 
               if k not in ["id", "type", "content", "model", "stop_reason", "usage"]}
    )


def internal_to_claude_code_resp(resp: InternalChatResponse) -> Dict[str, Any]:
    """
    内部格式 -> Claude Code 响应格式
    """
    last_msg = resp.messages[-1] if resp.messages else InternalMessage(
        role="assistant",
        content=[InternalContentBlock(type="text", text="")]
    )
    
    # 检查消息类型
    has_text = any(b.type == "text" for b in last_msg.content)
    has_tool_call = any(b.type == "tool_call" for b in last_msg.content)
    has_tool_result = any(b.type == "tool_result" for b in last_msg.content)
    
    # 根据内容类型构建响应
    if has_tool_result:
        # 工具结果消息
        tool_result_block = next(b.tool_result for b in last_msg.content if b.type == "tool_result")
        return {
            "type": "tool_result",
            "tool_name": tool_result_block.name,
            "result": tool_result_block.output,
            "tool_call_id": tool_result_block.call_id
        }
    
    elif has_tool_call:
        # 工具调用消息
        tool_call_block = next(b.tool_call for b in last_msg.content if b.type == "tool_call")
        return {
            "type": "tool_call",
            "id": tool_call_block.id,
            "tool_name": tool_call_block.name,
            "input": tool_call_block.arguments
        }
    
    else:
        # 普通助手消息
        content = []
        for b in last_msg.content:
            if b.type == "text" and b.text:
                content.append({"type": "text", "text": b.text})
        
        if not content:
            content = [{"type": "text", "text": ""}]
        
        return {
            "type": "assistant",
            "content": content,
            "model": resp.model,
            "id": resp.id,
            **resp.extra
        }