# AI4Math 示例中心 (Examples & Showcase)

本目录提供一套完整的 **AI4Math** 综合演示案例，涵盖 **精确符号计算**、**简单数学证明** 与 **数学可视化** 三大核心场景。

## 目录结构

| 文件 / 目录 | 说明 |
|---|---|
| [`demo_showcase.md`](demo_showcase.md) | **【推荐直接查看】** 由双引擎实跑生成的图文案例报告（含 LaTeX 推导、证明骨架与三张可视化图） |
| [`run_demo.py`](run_demo.py) | 一键演示脚本：默认离线调用 SymPy + SageMath 工具重新生成报告与图片；加 `--llm` 可走完整大模型问答 |
| [`demo_questions.md`](demo_questions.md) | 适用于 `ai4math -b` 批处理模式的三合一测试题集（计算 + 证明 + 可视化） |
| [`assets/`](assets/) | 演示脚本自动生成的函数图像、不等式交集区域图与复变函数色相图 |

## 快速体验方式

### 方式 1：无需 API Key，直接运行确定性工具引擎 Demo
```bash
conda activate ai4math
python examples/run_demo.py
```
脚本会依次调用 `compute_sum`、`galois_group`、`compute_variance`、`moment_generating_function`、`verify_conjecture`、`construct_proof`、`plot_function`、`plot_inequality_region` 和 `sage_complex_plot`，输出 [`demo_showcase.md`](demo_showcase.md) 并更新 [`assets/`](assets/) 下的图片。

### 方式 2：结合大模型 API 端到端体验（需配置 `.env`）
```bash
# 使用单脚本端到端模式
python examples/run_demo.py --llm

# 或使用 CLI 批量处理示例题单（3 道题：计算 + 证明 + 绘图）
ai4math -b examples/demo_questions.md -w 2 -o output/demo_batch
```
