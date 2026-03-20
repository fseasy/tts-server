## How to start dev

1. push to main
2. merge main to release, then it will trigger the deployment
3. pay attention to the self dependency of `fs_pyutils`: use  `uv sync --upgrade-package fs_pyutils` to sync if we have changed something.

-----

## 26.03.19

### 大坑：sqlite 目录不存在，异步创建 engine 就卡在那里

不报错，不启动，就 hang 在那里… 服了 
除去我没有创建文件夹的锅，这个不报错有点太坑了，不知道是我哪里漏了？还是怎么的。

### .gitignore `*` 把自己也给忽略了

```
*
!.gitignore
```

这样比较好！

### systemd conf 不支持行尾注释！

```
Type=simple # change to simple as LLM suggesting 这个怎么报错了
```

这种要报错！ => 事实证明，还是应该用 notify 模式！可以用，而且感觉更稳一点。

### BASH string 里用`\` 去反转义变量求值

之前一直没注意，原来 env-init.sh 里面写 systemd 的 `/bin/kill -s HUP $MAINPID` 里面的  $MAINPID 直接被替换为变量了—空变量！
幸好后面加了 `set -Eeuo pipefail` 才看到这个问题 …

## 26.03.17

### 跨域 preflight 

一个前端 fetch POST 请求，405 了，看浏览器，是走了 OPTIONS 请求，被返回 405.

这是经典的 CORS（跨域资源共享）预检请求（Preflight Request） 行为。
为什么会出现 OPTIONS 请求？
当浏览器发起“跨域”请求（例如你的网页在 localhost:1313，而 API 在 127.0.0.1:3101）且满足以下任一条件时，浏览器会自动在正式发送 POST 请求之前，先发送一个 OPTIONS 请求来询问服务器：
方法不是简单的 GET/POST/HEAD。
设置了自定义 Header（例如 Content-Type: application/json 就属于非简单请求）。
服务器返回 405 Method Not Allowed，说明你的后端 API（基于 FastAPI/Uvicorn）没有配置 CORS 支持，它不认识 OPTIONS 这个方法，所以拒绝了它。

解决方法是在后端增加允许跨域的配置。


## 26.03.15

### [TtsOptionT: TtsBaseOption] —— 泛型声明

这是 Python 3.12 引入的 泛型类型参数语法 (Generic Type Parameter Syntax)。它比旧式的 TypeVar 写法更简洁，语义也更直接。

### async AsyncGenerator 基类函数与子类函数签名冲突的问题

base:

```python
class TtsProviderTtsOptionT: TtsBaseOption:
@abstractmethod
async def synthesize(self, text: str, option: TtsOptionT | None = None) -> AsyncGenerator[bytes, None]:
pass
```

edge impl:

```python
class EdgeTtsProvider(TtsProvider[EdgeTtsOption]):
def init(self, option: EdgeTtsOption):
self._option = option
async def synthesize(self, text: str, option: EdgeTtsOption | None = None) -> AsyncGenerator[bytes, None]:
  ...

```

但是这里报错：
方法“synthesize”以不兼容的方式替代类“TtsProvider”
返回类型不匹配:基方法返回类型"CoroutineType[Any, Any, AsyncGenerator[bytes, None]]"，替代返回类型"AsyncGenerator[bytes, None]"
“AsyncGenerator[bytes, None]”不可分配给“CoroutineType[Any, Any, AsyncGenerator[bytes, None]]”PylancereportIncompatibleMethodOverride
base.py(9, 13): 替代的方法

Gemini 说是因为父类里面没有 yield, 所以被自动变成了协程，也就是 `CoroutineType[Any, Any, AsyncGenerator[bytes, None]]`, 加上一个 yield, 就可以了。

=> 加上后，果然就好使了… 

还有一种方法就是父类不要写 async，但有点理解不了，就算了。