"""
GuardianBridge (守桥) 主入口
FastAPI 应用启动文件
"""
import traceback
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ai_proxy.proxy.router import router
from ai_proxy.config import settings
from ai_proxy.moderation.smart.scheduler import start_scheduler
from ai_proxy.utils.memory_guard import check_all_tracked, check_process_memory

app = FastAPI(
    title="GuardianBridge",
    description="高级 AI API 中间件 - 智能审核 · 格式转换 · 透明代理",
    version="1.0.0"
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器 - 打印详细错误"""
    print(f"\n{'='*60}")
    print(f"[ERROR] Unhandled exception:")
    print(f"Path: {request.url.path}")
    print(f"Exception: {exc}")
    print(f"Traceback:")
    traceback.print_exc()
    print(f"{'='*60}\n")
    
    return JSONResponse(
        status_code=500,
        content={"error": {"message": str(exc), "type": type(exc).__name__}}
    )

# 全局标志：防止重复启动
_scheduler_started = False
_memory_guard_task = None

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    global _scheduler_started, _memory_guard_task
    
    print("[INFO] GuardianBridge 启动")
    
    # 防止重复启动调度器（reload模式下可能多次触发）
    if not _scheduler_started:
        start_scheduler(check_interval_minutes=10)
        _scheduler_started = True
        print("[INFO] 模型训练调度器已启动")
    
    # 启动内存守护后台任务（每30秒检查一次）
    _memory_guard_task = asyncio.create_task(memory_guard_loop())
    print("[INFO] 内存守护后台任务已启动")

async def memory_guard_loop():
    """内存守护后台循环 - 定期检查所有追踪的容器 + 进程总内存"""
    while True:
        try:
            await asyncio.sleep(30)  # 每30秒检查一次
            
            # 1. 检查容器内存
            cleared = check_all_tracked()
            if cleared > 0:
                print(f"[MEMORY_GUARD] 本次检查清空了 {cleared} 个超大容器")
            
            # 2. 检查进程总内存（兜底机制）
            check_process_memory()  # 如果超过2GB会自动退出
            
        except asyncio.CancelledError:
            print("[MEMORY_GUARD] 后台任务已取消")
            break
        except Exception as e:
            print(f"[MEMORY_GUARD] 后台任务异常: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    global _memory_guard_task
    
    print("[INFO] GuardianBridge 正在关闭...")
    
    # 取消内存守护任务
    if _memory_guard_task:
        _memory_guard_task.cancel()
        try:
            await _memory_guard_task
        except asyncio.CancelledError:
            pass
        print("[INFO] 内存守护任务已停止")
    
    # 清理 HTTP 客户端池
    from ai_proxy.proxy.upstream import cleanup_clients
    await cleanup_clients()
    print("[INFO] HTTP 客户端池已清理")
    
    # 清理 OpenAI 客户端
    from ai_proxy.moderation.smart.ai import cleanup_openai_clients
    await cleanup_openai_clients()
    print("[INFO] OpenAI 客户端池已清理")
    
    # 清理数据库连接池
    from ai_proxy.moderation.smart.storage import cleanup_pools
    cleanup_pools()
    print("[INFO] 数据库连接池已清理")
    
    # 清理关键词过滤器
    from ai_proxy.moderation.basic import cleanup_filters
    cleanup_filters()
    print("[INFO] 关键词过滤器已清理")
    
    print("[INFO] GuardianBridge 已关闭")

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "ai_proxy.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )