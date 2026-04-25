# 定理条目 Schema

每个领域文件（如 `algebraic_geometry.json`）的格式为：

```json
{
  "domain": "algebraic_geometry",
  "theorems": [ ... ]
}
```

也兼容旧格式 `{"theorems": [...]}` 和纯数组 `[...]`。

## 定理条目字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 唯一标识符，如 `weil_zeta_curve` |
| `name` | string | 是 | 英文名称 |
| `name_zh` | string | 否 | 中文名称 |
| `domains` | string[] | 是 | 所属领域列表，如 `["algebraic_geometry", "finite_fields"]` |
| `keywords` | string[] | 是 | 关键词列表，用于子串匹配（大小写不敏感） |
| `signals` | string[] | 是 | 正则表达式列表，用于模式匹配（+2 分/命中） |
| `applicable_when` | string | 否 | 适用场景描述 |
| `reduces` | string | 否 | 该定理如何降低计算复杂度 |
| `prerequisites` | string[] | 否 | 使用该定理前需要先计算的量 |
| `invariant_hints` | string[] | 否 | 建议优先求的中间不变量 |
| `verification_hints` | string[] | 否 | 最终答案前应检查的验证项 |
| `preferred_recipe` | string[] | 否 | 推荐的执行步骤（软约束，高置信度时优先提示给模型） |
| `avoid_patterns` | string[] | 否 | 应尽量避免的方法或失败模式（软约束，不是硬规则） |
| `confidence` | string / number | 否 | 该 theorem 对该类题的先验强度，如 `high`、`medium`、`0.9` |
| `sage_hint` | string | 否 | SageMath 代码提示 |
| `related` | string[] | 否 | 相关定理的 id 列表 |

## 匹配评分规则

- 每个命中的 `keywords` 条目：+1 分
- 每个命中的 `signals` 正则：+2 分
- 按总分降序排列，取前 6 个

## 新增定理条目

1. 在对应领域文件中添加条目（或新建领域文件）
2. 确保 `id` 全局唯一
3. 至少填写 `id`、`name`、`domains`、`keywords`、`signals`
4. 对于计算密集型问题，务必填写 `invariant_hints` 和 `verification_hints`
5. 运行测试验证：`python -m unittest tests.test_theorem_advisor_external`

## 新增领域文件

1. 在 `ai4math/tools/theorems/` 下创建 `<domain_name>.json`
2. 格式为 `{"domain": "<domain_name>", "theorems": [...]}`
3. 系统会自动发现并加载所有 `*.json` 文件
4. 跨文件的 `id` 重复条目会自动去重（保留先加载的）
