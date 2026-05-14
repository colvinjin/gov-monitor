"""
截图功能 - 使用 Playwright 截取网页界面
"""
import asyncio
from playwright.async_api import async_playwright
from typing import Optional
import os


async def capture_screenshot(
    url: str = "http://localhost:8000",
    output_path: str = "/tmp/screenshot.png",
    width: int = 1200,
    height: int = 800,
    wait_for_selector: Optional[str] = None,
    delay_ms: int = 1000
) -> str:
    """
    截取网页截图
    
    Args:
        url: 网页地址
        output_path: 输出路径
        width: 视口宽度
        height: 视口高度
        wait_for_selector: 等待特定元素出现
        delay_ms: 等待时间（毫秒）
    
    Returns:
        截图文件路径
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": width, "height": height})
        
        try:
            await page.goto(url, wait_until="networkidle")
            
            # 等待特定元素
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=5000)
            
            # 额外等待，确保页面渲染完成
            await page.wait_for_timeout(delay_ms)
            
            # 截取全页或视口
            await page.screenshot(path=output_path, full_page=True)
            
            await browser.close()
            
            return output_path
            
        except Exception as e:
            await browser.close()
            raise e


async def capture_training_interface() -> str:
    """截取训练界面（配置选择状态）"""
    return await capture_screenshot(
        url="http://localhost:8000",
        output_path="/tmp/training_interface.png",
        width=1200,
        height=800,
        wait_for_selector="#config",
        delay_ms=500
    )


async def capture_conversation() -> str:
    """截取对话界面（需要先有对话内容）"""
    return await capture_screenshot(
        url="http://localhost:8000",
        output_path="/tmp/conversation.png",
        width=1200,
        height=1000,
        wait_for_selector="#conversation",
        delay_ms=500
    )


# 同步包装函数
def screenshot(url: str = "http://localhost:8000", output: str = "/tmp/screenshot.png") -> str:
    """同步调用截图"""
    return asyncio.run(capture_screenshot(url, output))


def screenshot_interface() -> str:
    """截取训练界面"""
    return asyncio.run(capture_training_interface())


if __name__ == "__main__":
    # 测试截图
    result = asyncio.run(capture_training_interface())
    print(f"截图已保存: {result}")
