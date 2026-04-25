# AI4Math - LLM 数学工具调用系统

让大语言模型通过工具调用进行精确的符号数学计算，基于 **SymPy** + **SageMath** 双引擎，涵盖 **数学分析**、**抽象代数**、**概率论**、**数论**、**组合数学**、**可视化** 等领域。

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
| `galois_group` | 多项式的 Galois 群精确计算（适用于低次 n≤11） |
| `galois_group_chebotarev` | 基于 Chebotarev 密度的 Galois 群统计推断（适用于高次多项式 n>11） |
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

### 📈 可视化 (matplotlib)
| 工具 | 功能 |
|------|------|
| `plot_function` | 一元函数图像（支持多函数叠加） |
| `plot_parametric` | 参数曲线 (x(t), y(t)) |
| `plot_implicit` | 隐式曲线 f(x,y)=0 |
| `plot_inequality_region` | 不等式区域填充（支持多条件交集） |
| `plot_3d` | 三维曲面 z=f(x,y) |

### 📈 可视化 (SageMath)
| 工具 | 功能 |
|------|------|
| `sage_plot` | SageMath 函数绘图（支持多函数） |
| `sage_implicit_plot` | 隐式曲线 |
| `sage_region_plot` | 不等式区域 |
| `sage_plot_3d` | 3D 曲面 |
| `sage_complex_plot` | 复变函数色相图 |

### 🧠 预规划与定理顾问
| 组件 | 功能 |
|------|------|
| `theorem_advisor` | 在正式求解前估计计算规模、匹配可用定理、导出 `suggested_invariants` / `verification_checks` |
| preplanning stage | 先做快速分析，再用更强模型生成策略摘要，按 `theorem -> invariants -> verification` 顺序组织复杂题求解 |
| domain theorem plugins | 内置定理库按领域拆分为多个 JSON 文件，支持自动发现、外部覆盖与合并检索 |

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
- **DeepSeek V4**（默认）: `OPENAI_BASE_URL=https://api.deepseek.com/beta`（strict 模式）
- **DeepSeek**: `OPENAI_BASE_URL=https://api.deepseek.com`
- **本地 vLLM/Ollama**: `OPENAI_BASE_URL=http://localhost:8000/v1`
- 任何兼容 OpenAI API 的服务

常用高级配置：
- `AI4MATH_AUTO_ROUTE=true`：简单题走 flash，复杂题走 pro
- `AI4MATH_PREPLAN_ENABLED=true`：启用预规划阶段，先分析规模与定理再正式求解
- `AI4MATH_PREPLAN_MODEL=deepseek-v4-pro`：预规划使用的模型
- `AI4MATH_THEOREM_SOURCE=merge`：定理库来源，支持 `builtin` / `external` / `merge`
- `AI4MATH_THEOREM_EXTERNAL_PATH=/absolute/path/to/theorems.json`：外部定理库 JSON 文件
- `AI4MATH_THEOREM_EXTERNAL_URL=https://example.com/theorems.json`：外部定理库 URL

### 3. 通用骨架与领域插件

复杂题默认按下面的通用骨架组织：

```text
识别题型 / 规模 -> 选定 theorem / structure -> 求关键 invariants -> 做 verification -> 最终作答
```

当前 `theorem_advisor` 会显式导出：
- `suggested_theorems`
- `suggested_invariants`
- `verification_checks`
- `workflow = {"phases": ["theorem", "invariants", "verification"]}`

内置定理库已拆分为多个领域插件文件：

```text
ai4math/tools/theorems/
├── algebraic_geometry.json
├── algebraic_number_theory.json
├── algebra.json
├── combinatorics.json
├── elliptic_curves.json
├── modular_forms.json
├── number_theory.json
├── theorems.json
└── _schema.md
```

加载规则：
- 系统会自动发现并合并 `tools/theorems/*.json`
- `theorems.json` 保留为向后兼容的聚合入口
- 外部定理库仍可通过 `AI4MATH_THEOREM_EXTERNAL_PATH` / `AI4MATH_THEOREM_EXTERNAL_URL` 注入
- 重复 `id` 的条目会自动去重

### 4. 启动

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

### 5. 交互模式示例

```
You > 化简 sin(x)^2 + cos(x)^2

You > 计算 ∫₀^∞ x²e^(-x) dx

You > 在 GF(7) 上因式分解 x^8 - 1

You > 求多项式 x^4 - 2 的 Galois 群

You > 椭圆曲线 y^2 + y = x^3 - x^2 的秩和扭子群

You > 计算理想 <x^2+y^2-1, x-y> 的 Groebner 基

You > 画出 sin(x) 和 cos(x) 在 [-2π, 2π] 的图像

You > 画出 x²+y²<1 且 x>0 的区域

You > 画出复变函数 (z^2-1)/(z^2+1) 的色相图
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
│   │   ├── plotting.py          # 可视化工具 (matplotlib)
│   │   ├── theorem_advisor.py   # 规模分析、定理匹配、领域插件加载
│   │   ├── theorems/
│   │   │   ├── _schema.md       # 定理条目 schema 与维护说明
│   │   │   ├── algebraic_geometry.json
│   │   │   ├── algebraic_number_theory.json
│   │   │   ├── algebra.json
│   │   │   ├── combinatorics.json
│   │   │   ├── elliptic_curves.json
│   │   │   ├── modular_forms.json
│   │   │   ├── number_theory.json
│   │   │   └── theorems.json    # 聚合入口（向后兼容）
│   │   ├── sage_tools.py        # 高级数学工具 (SageMath)
│   │   ├── sage_plotting.py     # 可视化工具 (SageMath)
│   │   └── sage_subprocess.py   # SageMath 子进程隔离执行
│   └── llm/
│       ├── __init__.py
│       └── client.py            # LLM 客户端 + 预规划阶段
├── pyproject.toml
├── .env.example
└── README.md
```

## 架构设计

```text
用户输入
  -> theorem_advisor（规模估计 + 领域插件匹配 + suggested_invariants / verification_checks）
  -> preplanning（按 theorem -> invariants -> verification 组织策略）
  -> LLM (tool calling)
  -> 工具注册表
  -> SymPy (进程内) / SageMath (独立子进程)
  -> 结果返回
  -> LLM 解释
  -> Markdown 输出
```

1. **工具注册系统** (`registry.py`): 通过 `@math_tool` 装饰器自动注册并生成 OpenAI function calling JSON Schema（支持 DeepSeek V4 strict 模式）
2. **双计算引擎**: SymPy（轻量快速，进程内执行）+ SageMath（高级形式化运算，每次调用独立子进程隔离）
3. **SageMath 子进程隔离** (`sage_subprocess.py`): 所有 SageMath 工具调用在独立子进程中执行，超时后硬杀整个进程组，避免 Maxima/ECL 等子进程残留。超时可通过 `AI4MATH_TOOL_TIMEOUT` 环境变量配置（默认 120s）
4. **通用骨架** (`client.py` + `theorem_advisor.py`): 正式求解前先估计规模、匹配定理、导出中间不变量与 verification checks；对 `heavy` / `infeasible_brute_force` 题目强制要求先做 theorem -> invariants -> verification
5. **领域插件** (`tools/theorems/*.json`): 定理库按领域拆分，系统自动发现、合并并支持外部覆盖
6. **LLM 客户端** (`client.py`): 支持 OpenAI 兼容 API 的工具调用循环，DeepSeek V4 自动启用 thinking 推理模式
7. **Markdown 输出**: Obsidian 兼容格式，支持保存/复制

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

## 领域插件维护

### 1. 新增一个定理条目

1. 找到最接近的领域文件，例如：
   - `ai4math/tools/theorems/algebraic_geometry.json`
   - `ai4math/tools/theorems/number_theory.json`
   - `ai4math/tools/theorems/combinatorics.json`
2. 按 `ai4math/tools/theorems/_schema.md` 的字段约定添加条目
3. 对复杂题，尽量补全：
   - `prerequisites`
   - `invariant_hints`
   - `verification_hints`
   - `sage_hint`
   - `preferred_recipe`（高置信度步骤序列，注入预规划上下文）
   - `avoid_patterns`（禁止的低效路线）
   - `confidence`（`"high"` / `"medium"` / `"low"`，高置信度条目会触发强指导注入）
4. 运行测试：

```bash
python -m unittest tests.test_theorem_advisor_external
python -m unittest tests.test_preplanning
```

### 2. 新增一个领域插件文件

在 `ai4math/tools/theorems/` 下新增 `<domain>.json`：

```json
{
  "domain": "representation_theory",
  "theorems": [
    {
      "id": "character_orthogonality",
      "name": "Orthogonality relations of characters",
      "domains": ["representation_theory", "group_theory"],
      "keywords": ["character", "orthogonality", "irreducible representation"],
      "signals": ["character.*table", "orthogonality"],
      "applicable_when": "处理有限群特征标表与不可约表示",
      "reduces": "把特征标表计算化为正交关系约束",
      "prerequisites": ["conjugacy classes", "group order"],
      "invariant_hints": ["class sizes", "inner products of characters"],
      "verification_hints": ["check row/column orthogonality", "verify degree-sum formula"],
      "sage_hint": "G.character_table()"
    }
  ]
}
```

系统会自动发现并加载，无需改 Python 注册表。

### 3. 外部定理库维护

外部定理库仍支持：

```bash
export AI4MATH_THEOREM_SOURCE=merge
export AI4MATH_THEOREM_EXTERNAL_PATH=/absolute/path/to/theorems.json
```

或：

```bash
export AI4MATH_THEOREM_SOURCE=external
export AI4MATH_THEOREM_EXTERNAL_URL=https://example.com/theorems.json
```

说明：
- `builtin`：只用内置领域插件
- `external`：优先外部库，失败时回退到内置
- `merge`：内置与外部合并，按 `id` 去重

### 4. 维护原则

- 一个定理只保留一个全局唯一 `id`
- `keywords` 用于宽松召回，`signals` 用于精确命中
- `invariant_hints` 写“先算什么”，不要写大段解释
- `verification_hints` 写“最后检查什么”，优先放 bounds、small-case consistency、recurrence、结构兼容性
- 领域拆分是为了维护方便，不是运行时隔离；同一条目仍可出现在多个 `domains` 中

## TODO

- 给 planner 增加更细的题型标签，例如：证明题、有限域点数、椭圆曲线、Galois 群、Groebner 基、组合计数、概率分布化简等
- 让预规划阶段根据题型标签选择更明确的工具优先级和中间不变量模板
- 为外部定理库补充来源管理、可信度标记和冲突去重策略
- 给各领域插件补更多 few-shot 风格的 `invariant_hints` / `verification_hints` 模板
- 把 `theorem_advisor.py` 进一步拆成通用加载器、通用匹配器，以及按领域注册的 invariant extractor / verifier hooks，减少跨领域逻辑继续堆在单文件中的耦合

## 更新日志

### v0.2.3 — 2026-04-25
- **有限域曲线点数稳定性**：为 `weil_zeta_curve` 和 `klein_quartic_automorphisms` 定理条目补充 `preferred_recipe`、`avoid_patterns` 和 `confidence: "high"`，使预规划阶段能注入高置信度指导（明确 `count_points(g)` → Newton 恒等式路线），避免模型在手动枚举/`rational_points()` 等低效路线上空转
- **循环重试保护**：System Prompt 新增工具调用防空转规则——同一工具连续 3 次返回相同错误或可疑结果时强制切换方法
- **新增测试**：`test_weil_curve_gets_high_confidence_recipe`（preplanning 注入验证）、`test_weil_curve_soft_constraints_present`（theorem advisor 软约束验证）

### v0.2.2 — 2026-04-25
- **通用骨架**：复杂题的预规划与定理顾问统一按 `theorem -> invariants -> verification` 三阶段组织
- **领域插件**：内置定理库从单一 `theorems.json` 拆分为多个 `tools/theorems/*.json` 领域文件，系统自动发现并合并
- **结构化 advisor 输出**：`theorem_advisor` 现可导出 `suggested_invariants`、`verification_checks` 与 `workflow`
- **维护文档**：新增 `tools/theorems/_schema.md` 与 README 中的领域插件维护说明

### v0.2.1 — 2026-04-24
- **SageMath 子进程隔离**：所有 SageMath 工具调用改为独立子进程执行（`sage_subprocess.py`），超时后硬杀整个进程组（SIGTERM → SIGKILL），彻底解决 Maxima/ECL 孤儿进程残留问题
- **工具级超时**：`AI4MATH_TOOL_TIMEOUT` 环境变量控制单次工具调用超时（默认 120s），超时后自动返回错误并清理子进程，不影响后续调用
- **批处理稳定性**：多进程批处理中 SageMath 卡死不再污染 worker 进程，超时后可立即恢复处理下一题
- **新增高难度测试题**：`test_batch.md` 新增 3 道研究生级别测试（数论验证、椭圆曲线 Mordell-Weil 群、五次数域完整刻画）

### v0.2.0 — 2026-04-24
- **升级 DeepSeek V4**：默认模型从 `deepseek-chat` 切换到 `deepseek-v4-pro`
- **Thinking 推理模式**：V4 模型自动启用 thinking 深度推理，`AI4MATH_REASONING_EFFORT` 可调节推理强度（none/low/medium/high，默认 high）
- **Strict 工具调用**：启用 DeepSeek V4 strict 模式（Beta），工具参数严格遵循 JSON Schema，提升调用可靠性
- **自动路由**：根据任务难度自动选择 flash（快/便宜）或 pro（强/深度推理），`AI4MATH_AUTO_ROUTE=true` 开启
- **可视化工具**：新增 10 个绘图工具（matplotlib 5 个 + SageMath 5 个），支持函数图像、参数曲线、隐式曲线、不等式区域、3D 曲面、复变函数色相图，图片保存到 `output/plots/`
- **Beta 端点**：默认 base_url 切换到 `https://api.deepseek.com/beta`

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
