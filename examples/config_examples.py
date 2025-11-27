"""
配置示例 - 展示各种使用场景
"""
import json
import urllib.parse


def create_proxy_url(config: dict, upstream: str, proxy_host: str = "http://localhost:8000") -> str:
    """创建代理 URL（URL编码方式）"""
    cfg_str = json.dumps(config, separators=(',', ':'))
    cfg_enc = urllib.parse.quote(cfg_str, safe='')
    return f"{proxy_host}/{cfg_enc}${upstream}"


def create_proxy_url_with_env(env_key: str, upstream: str, proxy_host: str = "http://localhost:8000") -> str:
    """创建代理 URL（环境变量方式，URL更短）"""
    return f"{proxy_host}/!{env_key}${upstream}"


# 示例 1: 仅基础审核
config_basic_only = {
    "basic_moderation": {
        "enabled": True,
        "keywords_file": "configs/keywords.txt"
    },
    "smart_moderation": {
        "enabled": False
    },
    "format_transform": {
        "enabled": False
    }
}

# 示例 2: 基础 + 智能审核
config_with_smart = {
    "basic_moderation": {
        "enabled": True,
        "keywords_file": "configs/keywords.txt"
    },
    "smart_moderation": {
        "enabled": True,
        "profile": "default"
    },
    "format_transform": {
        "enabled": False
    }
}

# 示例 3: OpenAI -> Claude 转换（支持工具调用）
config_openai_to_claude = {
    "basic_moderation": {
        "enabled": False
    },
    "smart_moderation": {
        "enabled": False
    },
    "format_transform": {
        "enabled": True,
        "from": "openai_chat",
        "to": "claude_chat",
        "stream": "auto",
        "strict_parse": True  # 强制要求解析成功，失败则返回错误
    }
}

# 示例 4: 多来源自动检测
config_auto_detect = {
    "basic_moderation": {
        "enabled": True,
        "keywords_file": "configs/keywords.txt"
    },
    "smart_moderation": {
        "enabled": True,
        "profile": "default"
    },
    "format_transform": {
        "enabled": True,
        "from": "auto",  # 自动检测所有支持的格式
        "to": "openai_chat",
        "stream": "auto"
    }
}

# 示例 5: 指定多个来源格式
config_multi_source = {
    "basic_moderation": {
        "enabled": True,
        "keywords_file": "configs/keywords.txt"
    },
    "smart_moderation": {
        "enabled": False
    },
    "format_transform": {
        "enabled": True,
        "from": ["openai_chat", "claude_chat"],  # 只支持这两种
        "to": "openai_chat",
        "stream": "auto"
    }
}

# 示例 6: 完整配置（所有功能开启）
config_full = {
    "basic_moderation": {
        "enabled": True,
        "keywords_file": "configs/keywords.txt",
        "error_code": "BASIC_MODERATION_BLOCKED"
    },
    "smart_moderation": {
        "enabled": True,
        "profile": "default"
    },
    "format_transform": {
        "enabled": True,
        "from": "auto",
        "to": "openai_chat",
        "stream": "auto",
        "detect": {
            "by_path": True,
            "by_header": True,
            "by_body": True
        }
    }
}

# 示例 7: 严格解析模式（解析失败直接返回错误）
config_strict_parse = {
    "basic_moderation": {
        "enabled": False
    },
    "smart_moderation": {
        "enabled": False
    },
    "format_transform": {
        "enabled": True,
        "from": "openai_chat",  # 只接受 OpenAI 格式
        "to": "openai_chat",
        "strict_parse": True  # 如果不是 OpenAI 格式，直接返回错误
    }
}

# 示例 8: 禁用工具调用
config_disable_tools = {
    "basic_moderation": {
        "enabled": False
    },
    "smart_moderation": {
        "enabled": False
    },
    "format_transform": {
        "enabled": True,
        "from": "auto",  # 自动检测，但会排除 claude_code 和 openai_codex
        "to": "openai_chat",
        "disable_tools": True  # 禁用工具调用：拒绝包含工具的请求
    }
}

# 示例 9: 禁用工具调用 + 严格解析
config_disable_tools_strict = {
    "basic_moderation": {
        "enabled": True,
        "keywords_file": "configs/keywords.txt"
    },
    "smart_moderation": {
        "enabled": True,
        "profile": "default"
    },
    "format_transform": {
        "enabled": True,
        "from": "openai_chat",  # 只接受 OpenAI Chat 格式
        "to": "claude_chat",
        "strict_parse": True,  # 严格解析
        "disable_tools": True  # 禁用工具调用
    }
}


if __name__ == "__main__":
    # 生成示例 URL
    print("=" * 60)
    print("代理 URL 示例（URL编码方式）")
    print("=" * 60)
    
    print("\n1. 仅基础审核:")
    url1 = create_proxy_url(config_basic_only, "https://api.openai.com/v1")
    print(f"   {url1[:100]}...")
    print(f"   长度: {len(url1)} 字符")
    
    print("\n2. 基础 + 智能审核:")
    url2 = create_proxy_url(config_with_smart, "https://api.openai.com/v1")
    print(f"   {url2[:100]}...")
    print(f"   长度: {len(url2)} 字符")
    
    print("\n3. OpenAI -> Claude 转换:")
    url3 = create_proxy_url(config_openai_to_claude, "https://api.anthropic.com/v1")
    print(f"   {url3[:100]}...")
    print(f"   长度: {len(url3)} 字符")
    
    print("\n4. 自动检测格式:")
    url4 = create_proxy_url(config_auto_detect, "https://api.openai.com/v1")
    print(f"   {url4[:100]}...")
    print(f"   长度: {len(url4)} 字符")
    
    print("\n5. 完整配置:")
    url5 = create_proxy_url(config_full, "https://api.openai.com/v1")
    print(f"   {url5[:100]}...")
    print(f"   长度: {len(url5)} 字符")
    
    print("\n" + "=" * 60)
    print("代理 URL 示例（环境变量方式 - URL更短）")
    print("=" * 60)
    print("\n需要在 .env 文件中配置:")
    print("  PROXY_CONFIG_DEFAULT=<json配置>")
    print("  PROXY_CONFIG_CLAUDE=<json配置>")
    
    print("\n1. 使用 PROXY_CONFIG_DEFAULT:")
    url_env1 = create_proxy_url_with_env("PROXY_CONFIG_DEFAULT", "https://api.openai.com/v1")
    print(f"   {url_env1}")
    print(f"   长度: {len(url_env1)} 字符")
    
    print("\n2. 使用 PROXY_CONFIG_CLAUDE:")
    url_env2 = create_proxy_url_with_env("PROXY_CONFIG_CLAUDE", "https://api.anthropic.com/v1")
    print(f"   {url_env2}")
    print(f"   长度: {len(url_env2)} 字符")
    
    print("\n对比: 环境变量方式可节省 ~200+ 字符，避免数据库字段溢出")
    
    print("\n" + "=" * 60)
    print("特殊配置示例")
    print("=" * 60)
    
    print("\n1. 禁用工具调用 (disable_tools):")
    print("   - 自动排除 claude_code 和 openai_codex 格式")
    print("   - 拒绝包含 tools、tool_choice、tool calls 的请求")
    print("   - 覆盖 format_transform.from 配置")
    url8 = create_proxy_url(config_disable_tools, "https://api.openai.com/v1")
    print(f"   {url8[:100]}...")
    
    print("\n2. 禁用工具调用 + 严格解析:")
    print("   - 只接受不包含工具的 OpenAI Chat 格式")
    print("   - 格式不匹配或包含工具时返回详细错误信息")
    url9 = create_proxy_url(config_disable_tools_strict, "https://api.anthropic.com/v1")
    print(f"   {url9[:100]}...")
    
    print("\n" + "=" * 60)
    print("配置说明")
    print("=" * 60)
    print("""
disable_tools 配置项说明:
  - 功能: 禁用所有工具调用相关功能
  - 作用范围:
    1. 自动排除仅支持工具的格式 (claude_code, openai_codex)
    2. 检测并拒绝包含以下内容的请求:
       - tools 字段 (工具定义)
       - tool_choice 字段 (工具选择)
       - tool_call 类型的消息块 (工具调用)
       - tool_result 类型的消息块 (工具结果)
  - 优先级: 会覆盖 format_transform.from 配置
  - 错误信息: 返回清晰的错误提示，说明禁止使用工具
  
使用场景:
  - 限制用户只能使用简单对话，不允许工具调用
  - 避免某些上游 API 不支持工具调用导致的错误
  - 安全考虑：防止工具调用绕过审核机制
    """)