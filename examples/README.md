# AI4Math 示例中心 (Examples & Showcase)

本目录提供一套完整的 **AI4Math** 综合演示案例，涵盖 **精确符号计算**、**Riemann Zeta 函数专题**、**简单数学证明** 以及 **三维黎曼面与多维可视化** 四大核心场景。

## 目录结构

| 文件 / 目录 | 说明 |
|---|---|
| [`demo_showcase.md`](demo_showcase.md) | **【推荐直接查看】** 由双引擎实跑生成的图文案例报告（含符号推导、Riemann $\zeta(s)$ 零极点、证明骨架及 $z=\sqrt{x}$ 三维黎曼面等 5 张图像） |
| [`run_demo.py`](run_demo.py) | 一键演示脚本：默认离线调用 SymPy + SageMath + Matplotlib 工具重新生成报告与全部图片；加 `--llm` 可走完整大模型问答 |
| [`demo_questions.md`](demo_questions.md) | 适用于 `ai4math -b` 批处理模式的四合一测试题集（计算 + Riemann Zeta + 证明 + 黎曼面可视化） |
| [`assets/`](assets/) | 演示脚本自动生成的 $z=\sqrt{x}$ 三维黎曼面、$\zeta(s)$ 色相图、函数曲线、不等式区域及有理函数色相图 |

## 快速体验方式

### 方式 1：无需 API Key，直接运行确定性工具引擎 Demo
```bash
conda activate ai4math
python examples/run_demo.py
```
脚本会自动完成符号求值、Riemann $\zeta(s)$ 函数方程与临界线零点检验、模 24 整除性证明构造，并绘制 $z=\sqrt{x}$ 三维四维着色黎曼面等全部图像，输出至 [`demo_showcase.md`](demo_showcase.md)。

### 方式 2：结合大模型 API 端到端体验（需配置 `.env`）
```bash
# 使用单脚本端到端模式
python examples/run_demo.py --llm

# 或使用 CLI 批量处理示例题单（4 道题：计算 + Zeta + 证明 + 黎曼面绘图）
ai4math -b examples/demo_questions.md -w 2 -o output/demo_batch
```
