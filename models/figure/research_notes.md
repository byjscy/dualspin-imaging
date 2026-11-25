# 双通道偏振超分辨成像研究示意图说明

本图描述的是已确认的**研究目标和实现路线**：两张 96×96 强度图，经电子编码
形成一张 24×24 相位图，经过三个偏振敏感调制层，再分别读取左右旋圆偏振强度。
图中数字和相位图均为说明性素材，不是训练结果、实验重建图或性能证据。

## a：信息如何进入同一张编码图

电子编码器同时接收两张目标图，不是独立缩小它们，也不是把两张图直接相加：

\[
C=E_\psi(I_A,I_B),\qquad C\in[0,2\pi)^{24\times24}.
\]

编码图被加载到独立的反射式编码显示器。相干激光被其调制后进入三台完整的
液晶空间光调制设备。相位编码的内容由电子编码器和光学解码器共同学习，
并不要求低分辨图案肉眼看起来仍像输入数字。

当前参考实现将编码图定义为单张相位图。如果实际编码显示器只能做振幅调制，
必须修改入射场定义并重新联合训练，不能直接复用相位编码权重。

## b：三台反射式器件的实验路线

示意路线为：激光与偏振准备 → 独立编码 SLM → LCOS 1 → LCOS 2 → LCOS 3
→ 四分之一波片与偏振分光分析 → 两路强度接收。

三台设备是完整的反射式器件，而不是三片透射薄片。图 a 的三张薄板只是
三次等效调制算子的流程符号；图 b 才表示反射式折返实现。

QWP 将待分析的圆偏振基映射到 PBS 的两条线偏振分析轴，形成独立输出。
波片轴角、反射后偏振基变换和通道命名必须在实际装置中标定；这里没有给出
未经测量的安装角度、波片补偿值或商用器件内部结构。

Blender 文件中的 `01_Reflective_apparatus` 场景保留可编辑设备，
`02_Research_figure` 场景用于二维科研图排版。PPT 中的文字为原生文本；
三维设备插图由 Blender 渲染，不能在 PPT 中直接逐个编辑设备网格。

## c：一个液晶层如何耦合两个圆偏振分量

采用本地推导中的约定：

\[
|L\rangle=\frac1{\sqrt2}(1,i)^T,\qquad
|R\rangle=\frac1{\sqrt2}(1,-i)^T.
\]

在该圆偏振基中，理想各向异性延迟单元的矩阵为：

\[
J(\theta,\Gamma)=
\begin{pmatrix}
\cos(\Gamma/2)&-i\sin(\Gamma/2)e^{-i2\theta}\\
-i\sin(\Gamma/2)e^{+i2\theta}&\cos(\Gamma/2)
\end{pmatrix}.
\]

其中 θ 是局部光轴方向，Γ 是局部相位延迟。左旋输入包含“保留左旋”的分量，
以及带有 +2θ 相位的右旋转换分量；右旋输入对应保留右旋及带 −2θ 相位的
左旋转换分量。只有理想半波延迟 Γ=π 时，共偏振项才消失。原 TXT 使用 Γ=π/5，
因此不能把每层画成完全的 L↔R 交换器，也不能把两个通道当成互不耦合的标量传播。

本图中的分子方向只是有效光轴示意。**标准商用 LCOS 相位器件并不自动等价于
具有任意空间光轴分布的几何相位液晶。** 2K73 型号的真实 Jones 响应、相位响应、
配套波片及反射坐标变换需要测量后纳入模型。

## d：联合训练与“超分辨”如何定义

三层网络可写为：

\[
\mathbf E_\mathrm{out}=
P_3J_3P_2J_2P_1J_1P_0\mathbf E_\mathrm{in}(C),
\quad
\hat I_A=|E_L|^2,\quad\hat I_B=|E_R|^2.
\]

P 表示传播算子；在真实反射系统中，需要进一步包含坐标转换、像差和中继效应。
电子编码器参数 ψ 与三层空间调制参数共同最小化两路目标重建误差。

96/24=4，是每轴采样点数的目标倍率；单通道输出像素数是输入编码像素数的
16 倍。这些计数不能直接解释为获得了四倍光学分辨率、16 倍有效空间带宽，
更不能表明突破了衍射极限。两张任意高维图像也不能保证从一张低维编码中无损恢复；
学习先验、噪声、相位精度和器件容量决定了可重建内容。

至少需要在相同视场下使用独立测试图及分辨率靶，比较插值/无解码器等基线，
测量线对响应或 MTF，并报告两路 PSNR、SSIM、探测效率和串扰。MNIST 原始图像
为 28×28，将其缩放为 96×96 不能产生原本不存在的高频细节。

## 参考文献与参考方式

1. Işıl et al., *Super-resolution image display using diffractive decoders*,
   Science Advances 8, eadd3433 (2022).
   [正式论文](https://doi.org/10.1126/sciadv.add3433)；[开放预印本](https://arxiv.org/abs/2206.07281)。
   参考其将电子编码器、低分辨调制与衍射解码器串联，以及把概念图与分辨率测试分开呈现的方式。
   该文的透射器件和实验条件不同，其数值不是本项目结果。
2. *Polarization multiplexed diffractive computing: all-optical implementation of a group of linear transformations through a polarization-encoded diffractive network*,
   Light: Science & Applications (2022).
   [正文](https://doi.org/10.1038/s41377-022-00849-x)；[Fig. 1](https://www.nature.com/articles/s41377-022-00849-x/figures/1)。
   参考其输入/输出偏振编码和两通道访问的表达。该文的各向同性层与偏振器阵列不能视为本项目的液晶结构。
3. Liu et al., *Polarization-multiplexed diffractive neural networks for multi-task classification based on liquid crystals*,
   Optics Letters 50, 5446–5449 (2025).
   [论文](https://doi.org/10.1364/OL.571548)。
   参考液晶 Jones 建模的研究方向；该文任务为分类，并非本项目的双图超分辨重建。
4. 本地材料：`D:\srdd\偏振调制演化推导.pdf` 与 `D:\srdd\双通道偏振调制.txt`。

本次没有照搬论文图像，也没有声称已查明作者使用何种绘图软件。图中器件来自本项目
Blender 场景；白底、分区、细分隔线和颜色对应关系参考用户提供的 PPT 样图。

## 可用于图注的文字

**中文：** 双通道偏振超分辨重建的研究原理示意。两张 96×96 目标图像由电子编码器
联合转换为一张 24×24 相位图案；该图案产生的相干光场通过三个偏振敏感调制阶段，
在圆偏振分析后形成分别对应两个目标的强度输出。单层示意显示共偏振保留项及带有
相反几何相位符号的交偏振转换项。电子编码与光学参数联合优化。图示采样倍率及目标
外观用于说明研究目标，不代表已测得的分辨率提升或实验重建结果。

**English:** Concept of dual-channel polarization-based super-resolution reconstruction.
Two 96×96 target images are jointly encoded into one 24×24 phase pattern. The resulting
coherent field is processed by three polarization-sensitive modulation stages and analyzed
in the circular-polarization basis to form two intensity outputs. The effective single-layer
model retains both co-polarized and cross-polarized components. The electronic encoder
and optical modulation parameters are jointly optimized. Sampling ratios and target
appearances illustrate the design objective, not measured resolution or reconstruction performance.
