# AI4Math - LLM 数学工具调用系统

让大语言模型通过工具调用进行精确的符号数学计算，基于 **SymPy** + **SageMath** 双引擎，涵盖 **数学分析**、**抽象代数**、**概率论**、**数论**、**组合数学** 等领域。

输出格式为 Obsidian 兼容的 Markdown + LaTeX，可直接粘贴到笔记中。

## 功能概览

### 📐 数学分析 (SymPy)
| 工具 | 功能 |
|------|------|
| `simplify_expression` | 化简数学表达式 |
| `expand_expression` | 展开表达式 |
| `factor_expression` | 因式分解 |
| `differentiate` | 求导（支持偏导数、高阶导数） |
| `integrate` | 积分（定积分、不定积分） |
| `compute_limit` | 极限计算 |
| `series_expansion` | 泰勒/麦克劳林级数展开 |
| `solve_equation` | 求解方程 / 方程组 |
| `solve_ode` | 求解常微分方程 |
| `compute_sum` | 级数求和 |
| `matrix_operation` | 矩阵运算（行列式、逆、特征值等） |
| `trig_simplify` | 三角函数化简 |
| `step_by_step_simplify` | 逐步化简过程 |

### 🔢 抽象代数 (SymPy)
| 工具 | 功能 |
|------|------|
| `polynomial_operation` | 多项式环运算（GCD、LCM、因式分解、除法） |
| `named_group` | 生成命名群（S_n, Z_n, D_n, A_n） |
| `permutation_operation` | 置换运算（乘法、逆、阶、循环分解） |
| `quotient_ring_operation` | 商环运算 |
| `check_algebraic_structure` | 代数结构验证（群公理检验） |
| `minimal_polynomial` | 最小多项式计算 |

### 🎲 概率论 (SymPy)
| 工具 | 功能 |
|------|------|
| `distribution_info` | 概率分布信息（PDF、期望、方差） |
| `compute_expectation` | 期望 E[g(X)] |
| `compute_variance` | 方差 Var[X] |
| `compute_probability` | 概率 P(条件) |
| `moment_generating_function` | 矩母函数 MGF |
| `characteristic_function` | 特征函数 |
| `bayes_theorem` | 贝叶斯定理 |
| `covariance_correlation` | 协方差与相关系数 |
| `simplify_probability_expression` | 概率表达式化简 |

### 🔮 高级代数 (SageMath)
| 工具 | 功能 |
|------|------|
| `finite_field_polynomial` | 有限域 GF(p^n) 上多项式因式分解、不可约检验 |
| `groebner_basis` | 多项式理想的 Groebner 基计算 |
| `ideal_membership` | 理想成员检验 |
| `number_field_info` | 数域扩张：次数、Galois 群、判别式、类数 |
| `galois_group` | 多项式的 Galois 群 |
| `elliptic_curve_info` | 椭圆曲线：秩、扭子群、j-不变量、导子 |
| `advanced_group_theory` | 中心、换位子群、Sylow 子群、共轭类、特征标表 |
| `lattice_operation` | Smith 标准形、Hermite 标准形、LLL 格基约化 |

### 🔢 数论 (SageMath)
| 工具 | 功能 |
|------|------|
| `number_theory_operation` | 大整数分解、素性检验、欧拉函数、中国剩余定理、模逆 |

### 🎯 组合数学 (SageMath)
| 工具 | 功能 |
|------|------|
| `combinatorics_operation` | 整数分拆、Catalan 数、Stirling 数、Bell 数、Fibonacci、Bernoulli、生成函数 |

### ⚡ 通用执行器 (SageMath)
| 工具 | 功能 |
|------|------|
| `sage_eval` | 直接执行 SageMath 代码（万能工具，覆盖一切高级运算） |

## 快速开始

### 1. 环境设置

```bash
# 激活 conda 环境
conda activate ai4math

# 安装项目（开发模式）
pip install -e .
```

### 2. 配置 API

```bash
cp .env.example .env
# 编辑 .env 填入 API 密钥
```

支持的 API 后端：
- **OpenAI**: `OPENAI_BASE_URL=https://api.openai.com/v1`
- **DeepSeek**: `OPENAI_BASE_URL=https://api.deepseek.com`
- **本地 vLLM/Ollama**: `OPENAI_BASE_URL=http://localhost:8000/v1`
- 任何兼容 OpenAI API 的服务

### 3. 启动

```bash
# 交互模式
ai4math

# 命令行直接提问（单次模式）
ai4math "化简 sin(x)^2 + cos(x)^2"

# 从文件读取问题
ai4math -f question.md

# 管道输入
echo "求导 x^3 * sin(x)" | ai4math

# 提问并保存结果
ai4math -o result.md "正态分布 N(0,1) 的矩母函数"

# 复杂含参积分（保存结果 + 确定性输出）
ai4math -o result.md "求定积分，\$2\int_{0}^{\frac{\pi}{2}} (\sin \theta)^{2s-1} \cos(n\theta) \, d\theta\$ ，其中 n 是偶数，s是整数" -t 0

# 控制输出随机性（0=确定性，1=创造性）
ai4math -t 0.7 "用三种方法证明 √2 是无理数"
```

### 4. 交互模式示例

```
You > 化简 sin(x)^2 + cos(x)^2

You > 计算 ∫₀^∞ x²e^(-x) dx

You > 在 GF(7) 上因式分解 x^8 - 1

You > 求多项式 x^4 - 2 的 Galois 群

You > 椭圆曲线 y^2 + y = x^3 - x^2 的秩和扭子群

You > 计算理想 <x^2+y^2-1, x-y> 的 Groebner 基
```

**多行输入**（适合粘贴复杂问题或 Markdown）：

```
You > """
  ... 请帮我完成以下推导：
  ... 已知 X ~ Poisson(λ)，
  ... 1. 求 E[X(X-1)]
  ... 2. 由此推导 Var(X) = λ
  ... """
```

也可以用 `/ml` 命令进入多行模式，输入完毕后再 `"""` 或连续两个空行结束。

### CLI 命令

| 命令 | 说明 |
|------|------|
| `"""` 或 `/ml` | 进入多行输入模式 |
| `/tools` | 列出所有可用工具 |
| `/reset` | 重置对话历史 |
| `/copy` | 复制最后回答的 Markdown 到剪贴板 |
| `/last` | 显示原始 Markdown（手动复制） |
| `/save` | 保存整个对话为 .md 文件 |
| `/save last` | 仅保存最后回答 |
| `/save x.md` | 保存到指定文件 |
| `/help` | 显示帮助 |
| `/quit` | 退出 |

## 项目结构

```
ai4math/
├── ai4math/
│   ├── __init__.py
│   ├── cli.py                   # 交互式 CLI
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py          # 工具注册与 Schema 生成
│   │   ├── analysis.py          # 数学分析工具 (SymPy)
│   │   ├── algebra.py           # 抽象代数工具 (SymPy)
│   │   ├── probability.py       # 概率论工具 (SymPy)
│   │   └── sage_tools.py        # 高级数学工具 (SageMath)
│   └── llm/
│       ├── __init__.py
│       └── client.py            # LLM 客户端
├── pyproject.toml
├── .env.example
└── README.md
```

## 架构设计

```
用户输入 → LLM (tool calling) → 工具注册表 → SymPy / SageMath 计算引擎 → 结果返回 → LLM 解释 → Markdown 输出
```

1. **工具注册系统** (`registry.py`): 通过 `@math_tool` 装饰器自动注册并生成 OpenAI function calling JSON Schema
2. **双计算引擎**: SymPy（轻量快速）+ SageMath（高级形式化运算）
3. **LLM 客户端** (`client.py`): 支持 OpenAI 兼容 API 的工具调用循环
4. **Markdown 输出**: Obsidian 兼容格式，支持保存/复制

## 扩展

添加新工具只需在对应模块中定义函数并使用装饰器：

```python
from ai4math.tools.registry import math_tool

@math_tool(category="sage_algebra", description="我的新工具")
def my_tool(expr: str) -> str:
    """工具描述。

    Args:
        expr: 输入表达式
    """
    import sage.all as sa
    # 实现计算逻辑
    return json.dumps({"result": "..."})
```

工具会自动注册并生成对应的 JSON Schema 供 LLM 调用。

## 更新日志

### v0.1.5 — 2026-02-12
- **Temperature 控制**：新增 `-t` / `--temperature` 命令行参数和 `AI4MATH_TEMPERATURE` 环境变量，控制输出随机性（默认 `0.0`，确定性输出）
- **自动续写**：检测到 LLM 输出被 token 限制截断时，自动发送 "继续" 指令，无缝拼接完整回复
- **max_tokens 提升**：默认输出上限从 4096 提升到 8192，可通过 `AI4MATH_MAX_TOKENS` 环境变量自定义
- **工具结果自动嵌入**：每次工具调用的计算结果自动格式化为 Markdown 引用块插入输出，确保中间步骤不丢失
- **引用块公式修复**：后处理自动将 `> $$...$$` 拆出引用块，修复 Obsidian 中行间公式渲染问题
- **错误结果隐藏**：失败的工具调用不再出现在最终输出中，保持文档整洁

### v0.1.4 — 2026-02-12
- **解决复杂含参积分问题**：新增 `sage_integrate` 工具，支持 assumptions（integer/positive/even/odd 等），符号积分超时时自动枚举参数值供 LLM 推导规律
- **新增 `sage_simplify`**：SageMath 驱动的高级符号化简，支持 full_simplify、canonicalize_radical 等策略
- **System Prompt 改进**：增加工具选择策略，引导 LLM 对复杂问题优先选择 SageMath 工具，避免反复重试失败的 SymPy 调用
- **sage_eval 增强**：自动预声明常用变量、改进赋值检测逻辑、更好的错误信息
- **最大迭代次数**从 15 提升到 25，且可通过 `AI4MATH_MAX_ITERATIONS` 环境变量自定义
- 工具总数增至 **41 个**

### v0.1.3 — 2026-02-12
- **多行输入**：支持 `"""` 和 `/ml` 进入多行输入模式，可粘贴 Markdown 格式的复杂问题
- **命令行模式**：`ai4math "问题"` 直接提问、`-f` 从文件读取、管道输入 `echo ... | ai4math`、`-o` 保存结果

### v0.1.2 — 2026-02-12
- **新增 SageMath 引擎**：集成 SageMath 10.7，新增 11 个高级数学工具
  - 高级代数：有限域多项式分解、Groebner 基、理想成员检验、数域扩张、Galois 群、椭圆曲线、高级群论（Sylow 子群/共轭类/特征标表）、格运算（Smith/Hermite/LLL）
  - 数论：大整数分解、素性检验、欧拉函数、中国剩余定理、模逆
  - 组合数学：整数分拆、Catalan 数、Stirling 数、Bell 数、Fibonacci 数、Bernoulli 数、生成函数
  - 通用执行器 `sage_eval`：可直接执行任意 SageMath 代码
- 工具总数从 28 个增长至 **39 个**

### v0.1.1 — 2026-02-12
- **Markdown 输出**：LLM 回复格式改为 Obsidian 兼容的 Markdown + LaTeX
- 新增 CLI 命令：`/copy`（复制到剪贴板）、`/last`（查看原始 Markdown）、`/save`（保存为 .md 文件）

### v0.1.0 — 2026-02-12
- 项目初始化，基于 SymPy 实现 28 个数学工具
- 支持数学分析（13 个）、抽象代数（6 个）、概率论（9 个）
- LLM 客户端支持 OpenAI 兼容 API 的 tool calling
- 交互式 CLI（基于 Rich）
- 独立 conda 环境 `ai4math`（Python 3.12）
