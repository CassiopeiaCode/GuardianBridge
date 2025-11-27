"""
GuardianBridge (守桥) 主入口
FastAPI 应用启动文件
"""
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ai_proxy.proxy.router import router
from ai_proxy.config import settings
from ai_proxy.moderation.smart.scheduler import start_scheduler

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

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    print("[INFO] GuardianBridge 启动")
    # 启动模型训练调度器（每10分钟检查一次）
    start_scheduler(check_interval_minutes=10)
    print("[INFO] 模型训练调度器已启动")

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "ai_proxy.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )