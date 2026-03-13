import asyncio
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI()


# 定义前端传来的请求体
class TTSRequest(BaseModel):
    text: str


# ---------------------------------------------------------
# 【后端核心逻辑】：请求真实 TTS 服务，并流式转发
# ---------------------------------------------------------
async def fetch_audio_stream_from_backend(text: str):
    """
    这里模拟你请求下游真实 TTS 模型的逻辑。
    使用 httpx 进行异步请求，获取流并 chunked 转发给前端。
    """
    # ⚠️ 【注意】实际部署时，将下面的 URL 替换为你真实的 TTS 后端地址
    # backend_tts_url = "http://your-real-tts-server:8080/generate"

    # 模拟真实场景的代码如下（已注释，供你参考套用）：
    """
    async with httpx.AsyncClient() as client:
        req = client.build_request("POST", backend_tts_url, json={"text": text})
        r = await client.send(req, stream=True)
        async for chunk in r.aiter_bytes(chunk_size=4096):
            yield chunk
    """

    # 为了让你现在直接运行就能看效果，这里用“模拟生成”代替真实请求：
    # 模拟：分块返回一些伪造的二进制数据（前端会当做普通文件接收）
    # 现实中这里 yield 的是真实的音频字节流
    for i in range(5):
        await asyncio.sleep(0.2)  # 模拟推理的延迟
        yield b"mock_audio_data_chunk_" + str(i).encode()


@app.post("/api/tts")
async def proxy_tts_endpoint(req: TTSRequest):
    # 使用 StreamingResponse 将流“透传”给前端
    # 媒体类型根据你后端真实的音频格式修改，通常是 audio/mpeg 或 audio/wav
    return StreamingResponse(fetch_audio_stream_from_backend(req.text), media_type="audio/mpeg")


# ---------------------------------------------------------
# 【前端页面】：提供 HTML 和 JS，直接挂载在根目录
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def get_index():
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <title>TTS 句子点击播放测试</title>
        <style>
            body { font-family: sans-serif; max-width: 600px; margin: 40px auto; }
            .sentence { 
                padding: 15px; margin: 10px 0; 
                border: 1px solid #ddd; border-radius: 8px;
                cursor: pointer; transition: background-color 0.2s;
            }
            .sentence:hover { background-color: #f9f9f9; }
            /* 正在请求后端的加载状态 */
            .loading { background-color: #fff3e0 !important; border-color: #ffb74d; }
            /* 正在播放的状态 */
            .playing { background-color: #e8f5e9 !important; border-color: #81c784; }
            .status { font-size: 12px; color: #666; float: right; }
        </style>
    </head>
    <body>
        <h2>点击句子播放对应声音</h2>
        <p style="color:gray; font-size:14px;">（提示：点击第一句，没播完时立刻点击第二句，观察打断效果）</p>
        
        <div id="container">
            <div class="sentence" data-text="这是第一句话，欢迎体验 FastAPI 的流式转发。">
                这是第一句话，欢迎体验 FastAPI 的流式转发。<span class="status"></span>
            </div>
            <div class="sentence" data-text="当你点击这里，前一个声音会被立刻打断。">
                当你点击这里，前一个声音会被立刻打断。<span class="status"></span>
            </div>
            <div class="sentence" data-text="同时，如果前一个网络请求还没结束，也会被取消掉，节省带宽。">
                同时，如果前一个网络请求还没结束，也会被取消掉，节省带宽。<span class="status"></span>
            </div>
        </div>

        <script>
            let currentAudio = null;         // 全局单例 Audio 对象
            let abortController = null;      // 用于取消未完成的网络请求
            let activeElement = null;        // 当前活动的 DOM 元素

            // 恢复 UI 状态的辅助函数
            function resetUI() {
                if (activeElement) {
                    activeElement.classList.remove('playing', 'loading');
                    activeElement.querySelector('.status').innerText = '';
                }
            }

            document.querySelectorAll('.sentence').forEach(el => {
                el.addEventListener('click', async () => {
                    const text = el.getAttribute('data-text');
                    
                    // ==========================================
                    // 1. 【核心】打断操作：清理音频和网络请求
                    // ==========================================
                    
                    // a) 停止当前正在播放的音频
                    if (currentAudio) {
                        currentAudio.pause();
                        currentAudio.removeAttribute('src'); // 彻底清空
                        currentAudio = null;
                    }

                    // b) 取消正在进行的 Fetch 请求（如果用户在前一句还没 loading 完就点了下一句）
                    if (abortController) {
                        abortController.abort(); 
                    }
                    
                    // 清理上一个元素的 UI
                    resetUI();

                    // ==========================================
                    // 2. 初始化新的请求状态
                    // ==========================================
                    activeElement = el;
                    activeElement.classList.add('loading');
                    activeElement.querySelector('.status').innerText = '加载中...';
                    
                    // 创建新的 AbortController 控制器
                    abortController = new AbortController();

                    try {
                        // ==========================================
                        // 3. 发送请求并接收流 (聚合成 Blob)
                        // ==========================================
                        const response = await fetch('/api/tts', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ text }),
                            signal: abortController.signal  // 绑定中断信号
                        });

                        if (!response.ok) throw new Error('网络响应异常');

                        // 这一步会一直等待，直到 Server 的流彻底传输完毕
                        const blob = await response.blob(); 
                        
                        // 为了本地能正常发声测试（因为 mock 的是不合法音频），
                        // 这里我们偷偷换成一个真实的简短测试提示音供你听效果：
                        // 【现实中】你应该直接用：const objectUrl = URL.createObjectURL(blob);
                        // ----------- 测试专用代码开始 -----------
                        const dummyAudioUrl = "https://actions.google.com/sounds/v1/ui/button_click.ogg";
                        const objectUrl = dummyAudioUrl; // 现实中请替换回 URL.createObjectURL(blob)
                        // ----------- 测试专用代码结束 -----------

                        // ==========================================
                        // 4. 播放完整音频
                        // ==========================================
                        currentAudio = new Audio(objectUrl);
                        
                        // 监听播放开始
                        currentAudio.onplay = () => {
                            activeElement.classList.remove('loading');
                            activeElement.classList.add('playing');
                            activeElement.querySelector('.status').innerText = '播放中...';
                        };
                        
                        // 监听播放结束
                        currentAudio.onended = () => {
                            resetUI();
                            // 释放内存，防止长时间使用导致浏览器内存泄漏
                            if(objectUrl !== dummyAudioUrl) URL.revokeObjectURL(objectUrl); 
                        };

                        await currentAudio.play();

                    } catch (error) {
                        // 捕获由 abortController 引发的打断异常
                        if (error.name === 'AbortError') {
                            console.log(`被用户主动打断: ${text}`);
                        } else {
                            console.error('TTS 获取或播放失败:', error);
                            resetUI();
                            activeElement.querySelector('.status').innerText = '❌ 失败';
                        }
                    }
                });
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
