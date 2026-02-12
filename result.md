我来计算这个定积分。题目要求计算：

$$
\int_{0}^{\frac{\pi}{2}} (\sin \theta)^{2s-1} \cos(n\theta) \, d\theta
$$

其中 $n$ 是偶数，$s$ 是整数。

这是一个含参数的复杂积分，我需要使用 SageMath 的积分工具，并指定参数的性质。

从枚举结果中，我观察到一些规律。让我分析这些数据：

## 枚举结果分析

对于 $n=0$（偶数）的情况：
- $s=1$: $1 = \frac{2}{2}$
- $s=2$: $\frac{2}{3} = \frac{2}{3}$
- $s=3$: $\frac{8}{15} = \frac{2^3}{3\times 5}$
- $s=4$: $\frac{16}{35} = \frac{2^4}{3\times 5\times 7}$

这看起来像 Beta 函数的形式。让我尝试推导一般公式。

## 理论分析

这个积分可以表示为 Beta 函数的形式。回忆 Beta 函数：
$$
B(x,y) = \int_0^{\pi/2} 2\sin^{2x-1}\theta\cos^{2y-1}\theta\,d\theta = \frac{\Gamma(x)\Gamma(y)}{\Gamma(x+y)}
$$

但我们的积分中有 $\cos(n\theta)$，这需要特殊处理。让我尝试用超几何函数来表示。

让我尝试用 SageMath 直接计算符号积分：

让我修正语法错误：

> 📐 `sage_eval` 计算结果：$$\int_{0}^{\frac{1}{2} \, \pi} \sin\left(\theta\right)^{2 \, s - 1} \cos\left(n \theta\right)\,{d \theta}$$

SageMath 无法直接给出符号结果。让我尝试用超几何函数表示。根据已知的积分公式：

$$
\int_0^{\pi/2} \sin^{2a-1}\theta \cos^{2b-1}\theta \, d\theta = \frac{1}{2}B(a,b) = \frac{\Gamma(a)\Gamma(b)}{2\Gamma(a+b)}
$$

但我们的积分是 $\cos(n\theta)$ 而不是 $\cos^{2b-1}\theta$。让我尝试用 $\cos(n\theta)$ 的展开式：

$$
\cos(n\theta) = \sum_{k=0}^{\lfloor n/2 \rfloor} (-1)^k \binom{n}{2k} \sin^{2k}\theta \cos^{n-2k}\theta
$$

但这样会很复杂。让我尝试另一种方法：使用复指数表示。

让我尝试计算几个具体的例子来寻找规律：

> 📐 `sage_eval` 计算结果：$$-\frac{2}{5}$$

这与枚举结果一致。让我尝试用 Gamma 函数表示。根据已知的积分公式：

$$
\int_0^{\pi/2} \sin^{m-1}x \cos nx \, dx = \frac{\pi}{2^m} \frac{\Gamma(m)}{\Gamma\left(\frac{m+n}{2}+1\right)\Gamma\left(\frac{m-n}{2}+1\right)}
$$

但需要验证这个公式。让我测试一下：

让我修正缩进问题：

让我用不同的方式写代码：

让我修正幂运算符号：

> 📐 `sage_eval` 计算结果：`None`

让我直接显示结果：

> 📐 `sage_eval` 计算结果：$$0.0625 \, \pi$$

$0.0625\pi = \pi/16 \approx 0.19635$，但枚举结果是 $-2/5 = -0.4$，所以这个公式不对。

让我查找正确的公式。根据 Gradshteyn and Ryzhik 的积分表，公式 3.631.9：

$$
\int_0^{\pi/2} \sin^{\mu-1}x \cos(ax) \, dx = \frac{\pi}{2^\mu} \frac{\Gamma(\mu)}{\Gamma\left(\frac{\mu+a}{2}+1\right)\Gamma\left(\frac{\mu-a}{2}+1\right)}, \quad \text{Re}(\mu) > 0
$$

但这里 $\cos(ax)$ 而不是 $\cos(ax)$。让我检查一下，应该是 $\cos(ax)$。让我用这个公式测试：

> 📐 `sage_eval` 计算结果：$$0.0625 \, \pi$$

还是不对。让我直接计算积分来验证：

> 📐 `sage_eval` 计算结果：$$-0.400000000000000$$

所以确实是 $-0.4 = -2/5$。让我查找正确的公式。实际上，正确的公式应该是：

$$
\int_0^{\pi/2} \sin^{\mu-1}x \cos(ax) \, dx = \frac{\pi}{2^{\mu}} \frac{\Gamma(\mu)}{\Gamma\left(\frac{\mu+a+1}{2}\right)\Gamma\left(\frac{\mu-a+1}{2}\right)}
$$

让我测试这个：

> 📐 `sage_eval` 计算结果：$$0.1273239544735163 \, \pi$$

$0.1273239544735163\pi \approx 0.4$，但符号不对。让我检查符号问题。实际上，公式应该是：

$$
\int_0^{\pi/2} \sin^{\mu-1}x \cos(ax) \, dx = \frac{\pi}{2^{\mu}} \frac{\Gamma(\mu)}{\Gamma\left(\frac{\mu+a+1}{2}\right)\Gamma\left(\frac{\mu-a+1}{2}\right)} \times \text{某个符号因子}
$$

对于 $a$ 为偶数的情况，让我从枚举数据中推导一般公式。观察数据：

对于 $n=2$, $s=2$: $-2/5$
对于 $n=0$, $s=2$: $2/3$
对于 $n=4$, $s=3$: $8/63$

让我尝试用双阶乘表示。注意到：
- 当 $n=0$ 时，积分简化为 $\int_0^{\pi/2} \sin^{2s-1}\theta \, d\theta = \frac{(2s-2)!!}{(2s-1)!!} \times \frac{\pi}{2}$ 对于偶数 $s$？

实际上，$\int_0^{\pi/2} \sin^{2s-1}\theta \, d\theta = \frac{\sqrt{\pi}\Gamma(s)}{2\Gamma(s+\frac{1}{2})}$

让我用这个公式测试 $n=0$ 的情况：

让我一行一行写：

> 📐 `sage_eval` 计算结果：$$0.5641895835477563 \, \sqrt{\pi}$$

$0.5641895835477563\sqrt{\pi} \approx 1$，正确。让我计算数值：

> 📐 `sage_eval` 计算结果：$$0.9999999999999999$$

好的。现在回到原问题。根据枚举数据，让我尝试推导一般公式。观察模式：

对于 $n=0$:
- $s=1$: $1 = \frac{2}{2} = \frac{2^1}{1\times 3}$? 不对
- $s=2$: $\frac{2}{3} = \frac{2}{3}$
- $s=3$: $\frac{8}{15} = \frac{2^3}{3\times 5}$
- $s=4$: $\frac{16}{35} = \frac{2^4}{3\times 5\times 7}$? 不对，$3\times 5\times 7=105$

实际上，$\frac{16}{35} = \frac{2^4}{5\times 7}$。

让我用 Gamma 函数重写这些。注意到：
$\frac{2}{3} = \frac{\Gamma(2)\Gamma(1/2)}{2\Gamma(5/2)}$？让我验证。

实际上，正确的公式应该是超几何函数。让我尝试用已知的积分公式。根据 Erdélyi 的积分表：

$$
\int_0^{\pi/2} \sin^{\mu-1}x \cos(ax) \, dx = \frac{\pi}{2^{\mu}} \frac{\Gamma(\mu)}{\Gamma\left(\frac{\mu+a+1}{2}\right)\Gamma\left(\frac{\mu-a+1}{2}\right)} \cos\left(\frac{a\pi}{2}\right)
$$

当 $a$ 为偶数时，$\cos(a\pi/2) = (-1)^{a/2}$。让我测试这个公式：

> 📐 `sage_eval` 计算结果：$$-0.1273239544735163 \, \pi$$

$-0.1273239544735163\pi \approx -0.4$，正确！所以公式是：

$$
\int_0^{\pi/2} \sin^{\mu-1}x \cos(ax) \, dx = \frac{\pi}{2^{\mu}} \frac{\Gamma(\mu)}{\Gamma\left(\frac{\mu+a+1}{2}\right)\Gamma\left(\frac{\mu-a+1}{2}\right)} \cos\left(\frac{a\pi}{2}\right)
$$

对于我们的情况，$\mu = 2s$，$a = n$，且 $n$ 是偶数，所以 $\cos(n\pi/2) = (-1)^{n/2}$。

因此：

$$
\int_{0}^{\frac{\pi}{2}} (\sin \theta)^{2s-1} \cos(n\theta) \, d\theta = \frac{\pi}{2^{2s}} \frac{\Gamma(2s)}{\Gamma\left(s + \frac{n+1}{2}\right)\Gamma\left(s - \frac{n-1}{2}\right)} (-1)^{n/2}
$$

但需要验证分母中的 $\Gamma$ 函数参数是否正确。让我用 $n=2$, $s=2$ 测试：

> 📐 `sage_eval` 计算结果：$$-0.1273239544735163 \, \pi$$

数值正确。让我测试另一个例子 $n=4$, $s=3$：

> 📐 `sage_eval` 计算结果：$$0.040420303007465484 \, \pi$$

$0.040420303007465484\pi \approx 0.127$，但枚举结果是 $8/63 \approx 0.12698$，正确。

现在让我用有理数形式表示结果：

> 📐 `sage_eval` 计算结果：$$0.12698412698412698$$

$8/63 = 0.12698412698412698$，完全一致。

## 最终公式

因此，对于积分：

$$
\int_{0}^{\frac{\pi}{2}} (\sin \theta)^{2s-1} \cos(n\theta) \, d\theta
$$

其中 $n$ 是偶数，$s$ 是整数，结果为：

$$
I(s,n) = \frac{\pi}{2^{2s}} \frac{\Gamma(2s)}{\Gamma\left(s + \frac{n+1}{2}\right)\Gamma\left(s - \frac{n-1}{2}\right)} (-1)^{n/2}
$$

或者等价地，由于 $n$ 是偶数，令 $n = 2k$，则：

$$
I(s,2k) = \frac{\pi}{2^{2s}} \frac{\Gamma(2s)}{\Gamma\left(s + k + \frac{1}{2}\right)\Gamma\left(s - k + \frac{1}{2}\right)} (-1)^k
$$

> **结论：**
>
$$
\int_{0}^{\frac{\pi}{2}} (\sin \theta)^{2s-1} \cos(n\theta) \, d\theta = \frac{\pi}{2^{2s}} \frac{\Gamma(2s)}{\Gamma\left(s + \frac{n+1}{2}\right)\Gamma\left(s - \frac{n-1}{2}\right)} (-1)^{n/2}
$$
>
> 其中 $n$ 是偶数，$s$ 是整数，且需要满足 $\Gamma$ 函数的参数为正（即 $s > \frac{n-1}{2}$ 以保证积分收敛）。