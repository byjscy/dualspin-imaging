# 双通道电子编码与有效 Jones 衍射重建

## 状态与用途

`dual_sr.py` 是新写的研究参考实现，不是原分类程序的改名版本。它实现
两张 96×96 强度图 → 一张 24×24 相位编码 → 三个有效 Jones 调制层 → 两个
96×96 圆偏振强度输出。尚未在本项目中完成训练，也没有提供训练权重。

检查环境未安装 PyTorch，因此交付时完成的是 Python 语法检查和无依赖的
Jones 矩阵数学自检；张量、梯度自检和训练需要在配置好 PyTorch 的环境运行。
数学自检不等于整个训练程序的运行验证。

## 相比原 TXT 的主要变化

- 将分类探测器和分类损失替换为双图重建输出与像素级重建损失。
- 输入两张图，电子编码器产生唯一的一张 24×24 相位图；不是把两张图缩小后拼接。
- 24×24 相位图以 4×4 采样保持块扩展到 96×96，表示同一视场中的低分辨调制单元。
- 使用一致的圆偏振基、完整的共偏振和交偏振项；默认 Γ=π/5，未假设理想半波片。
- 三层独立的空间调制图与电子编码器联合训练，分别保存相位图和原始预测强度。
- 角谱传播使用 fftfreq 与不移位 FFT；在双精度中构造去载波传递函数，减少大相位误差。
- 使用 192×192 扩展传播窗口、有限孔径及输出裁剪，分别记录入射功率、各层功率和探测功率。
- PSNR/SSIM 采用同一目标定义的强度范围，不分别拉伸输出图像来掩盖效率或串扰问题。
- 固定随机种子、独立测试集、checkpoint 配置检查、梯度裁剪和独立自检入口。

## 安装与运行

在你用于训练的 Python 环境安装 PyTorch、NumPy、Pillow；读取 MNIST 还需要
与 PyTorch 匹配的 torchvision。GPU 是否可用由该环境的 PyTorch/CUDA 安装决定，
与 Blender 的 OptiX 设置相互独立。

```powershell
python D:\srdd\code\dual_sr.py --physics-check
python D:\srdd\code\dual_sr.py --self-test
```

先进行少量程序化数字的流程测试（不是 MNIST 性能实验）：

```powershell
python D:\srdd\code\dual_sr.py --dataset synthetic --limit 64 --epochs 1 --batch-size 4 --output D:\srdd\models\figure\smoke_run
```

使用真实 MNIST 训练，首次获取数据需显式允许下载：

```powershell
python D:\srdd\code\dual_sr.py --dataset mnist --download --data D:\srdd\data --limit 4096 --epochs 30 --output D:\srdd\models\figure\mnist_run
```

仅评估已训练权重，光学参数必须与训练时一致：

```powershell
python D:\srdd\code\dual_sr.py --dataset mnist --data D:\srdd\data --checkpoint D:\srdd\models\figure\mnist_run\last.pt --eval-only --output D:\srdd\models\figure\eval_run
```

输出包括 `last.pt`、`results.json`、24×24 相位、三层 beta=2θ 参数、未归一化预测强度、
目标强度与可视化图。训练指标仅在实际运行后产生；当前示意图没有使用这些未生成的结果。

## 物理约定与边界

圆偏振基按本地 PDF：L=(1,i)/√2，R=(1,−i)/√2。

```
J = [[ cos(Γ/2),            -i sin(Γ/2) exp(-i beta)],
     [-i sin(Γ/2) exp(+i beta),          cos(Γ/2)   ]]
beta = 2 theta
```

原 TXT 的可训练相位 M 出现在相反号指数中；与本约定比较时可用 M=-2θ 对应，
不能混用相位符号后再把差异解释为物理偏振旋向变化。反射系统的左右旋命名还必须
同时注明观察方向并逐镜变换局部坐标基。

这是三层理想无损各向异性薄单元的有效模型。有限孔径与探测裁剪允许功率损失，
但单元 Jones 变换本身守恒。默认传播参数只是参考仿真配置，不是从 Blender
设备间距读出的实验参数。裸商用反射式 LCOS 不能仅凭名称就等同于任意空间 θ(x,y)
的几何相位液晶；真实 2K73 的电压-相位响应、偏振响应、反射坐标变换、波片角度、
像差和中继关系需要标定后替换进前向模型。本程序不直接向设备加载灰度图。

96/24=4 是线性采样倍率，单通道输出像素数为编码像素数的 16 倍。两张任意高维图像
不能因进入一张低维相位图就保证无损恢复；重建依赖训练先验、编码精度与系统容量。
保持相同视场、独立分辨率靶/线对响应或 MTF、与插值基线的比较、噪声与串扰测试
才支持实际分辨率结论。MNIST 原图仅 28×28，缩放到 96×96 不会创造真实高频细节。

## 文献

1. Işıl et al., *Super-resolution image display using diffractive decoders*.
   https://arxiv.org/abs/2206.07281
2. *Polarization multiplexed diffractive computing*, Light: Science & Applications (2022).
   https://doi.org/10.1038/s41377-022-00849-x
3. Liu et al., *Polarization-multiplexed diffractive neural networks for multi-task classification based on liquid crystals*, Opt. Lett. 50, 5446–5449 (2025).
   https://doi.org/10.1364/OL.571548

这些文献提供编码-衍射解码、偏振复用和液晶 Jones 建模的参考，并非本项目实际性能证据。
