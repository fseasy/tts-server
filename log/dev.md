## 26.03.15

## [TtsOptionT: TtsBaseOption] —— 泛型声明

这是 Python 3.12 引入的 泛型类型参数语法 (Generic Type Parameter Syntax)。它比旧式的 TypeVar 写法更简洁，语义也更直接。

## async AsyncGenerator 基类函数与子类函数签名冲突的问题

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