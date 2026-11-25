# 双通道偏振成像程序（Windows / CUDA）

主程序：`polar_sr_cuda.py`。与旧版 `dual_sr.py` 独立，不覆盖旧程序。

## 运行流程

两张 MNIST 灰度图先插值为 96×96，作为有序的 A/B 输入；电子卷积编码器生成**一张 24×24 相位图**（0～2π）。编码图以 4×4 恒相位宏像素加载到 96×96 的有限照明窗口。单位功率左旋圆偏振光经过三层相干 Jones 耦合与角谱传播，输出左旋 A 与右旋 B 的两个 96×96 光强窗口。没有数字解码网络在光学输出后补画图像。

参考 txt 原本是十分类和偏振差分探测任务，不能直接实现这项重建任务。本版本保留三层耦合矩阵及参考的 532 nm、8 μm、gamma=π/5、传播距离和介质折射率参数，将分类探测器改为双通道图像损失，联合训练编码器与三层调制图。

## 安装

建议 Python 3.12、NVIDIA 显卡和最新兼容驱动。在 PowerShell 中：

```powershell
cd D:\srdd\code
py -3.12 -m venv .venv_polar
.\.venv_polar\Scripts\python.exe -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124
.\.venv_polar\Scripts\python.exe -m pip install numpy pillow
.\.venv_polar\Scripts\python.exe -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

如使用不同硬件/版本，以 [PyTorch 官方安装选择器](https://pytorch.org/get-started/locally/)中的 Windows / Pip / CUDA 命令为准。这个程序不依赖 torchvision。CUDA 轮子含运行时，常规运行不需要自行编译 CUDA Toolkit。程序默认要求 CUDA，不能用时会报错，不会悄悄改用 CPU。

## 数据位置与全局配置

打开主程序最上方 CONFIG，首先设置 `mnist_dir`、`epochs`、`batch_size` 和 `output_dir`。

`mnist_dir` 支持递归查找原始 MNIST IDX 文件，不是任意 PNG 图片文件夹：

```text
D:\datasets\MNIST\
  train-images-idx3-ubyte.gz
  t10k-images-idx3-ubyte.gz
```

可以解压后去掉 `.gz`，也可以放在 `MNIST\raw` 子目录。重建不使用分类标签，因此不要求 labels 文件。`download_mnist=True` 时可自动下载缺失图像文件。

| 配置 | 默认 | 作用 |
|---|---:|---|
| epochs | 80 | 总训练轮数，续训时也表示总轮数 |
| batch_size | 8 | 8GB 显存的起始配置；不足时改 4/2 |
| learning_rate | 0.001 | 编码器与三层光学参数的学习率 |
| num_workers | 0 | Windows 稳定默认，磁盘加载可尝试 2 |
| wavelength_m | 532e-9 | 默认 532 nm 绿光；实物 520 nm 应改为 520e-9 |
| slm_size | 200 | 每层有效计算网格，不等于真实设备分辨率 |
| padding | 100 | 零填充边界；发表前应做增加 padding 的收敛性测试 |
| segments | 见代码 | 四段光路内每段的距离（米）和折射率 |
| retardance_rad | π/5 | 固定双折射延迟，沿用参考，不作为实测值 |
| target_total_power | 0.10 | 两通道目标 ROI 总功率为入射光的 10%，各分 5% |
| amp_encoder | True | 仅 GPU 编码器使用混合精度；光学始终 complex64 |
| train_limit/test_limit | 0 | 0 为全部；可以限量验证程序流程 |
| val_size | 5000 | 官方训练集划出的验证样本数 |
| checkpoint | 空 | 恢复训练或测试时指定本程序保存的权重 |
| mode | train | train 联合训练；test 只评估 checkpoint |

## 启动与结果

```powershell
cd D:\srdd\code
.\.venv_polar\Scripts\python.exe polar_sr_cuda.py --self-test
.\.venv_polar\Scripts\python.exe polar_sr_cuda.py
```

无需在 PowerShell 执行激活脚本。Windows 的入口保护与 freeze_support 已处理。数据准备/存盘仍使用 CPU，这是正常分工。GPU 编码、复数传播、梯度均在 CUDA；没有使用半精度 FFT，因为其形状支持有限，见 [PyTorch fft2 文档](https://docs.pytorch.org/docs/stable/generated/torch.fft.fft2.html)。

输出到 `output_dir` 下的新时间文件夹：

- `best.pt`：当前训练产生的验证最优检查点；`last.pt`：最后一轮，可续训（包含优化器和历史最优参数）。
- `config.json`、`environment.json`：完整参数和运行环境。
- `split_indices.npz`：训练/验证原始索引；两者不重叠，测试使用官方 t10k 数据。
- `history.csv`：训练/验证损失和时间。
- `test_metrics.csv`、`test_summary.json`：逐样本和均值 PSNR/SSIM、两个通道 ROI 效率和全窗口功率。
- `tested_checkpoint.txt`：实际用于评估的模型来源。
- `sample_0000` 等：两输入、24×24 编码图、两输出、对照图及无显示裁剪的原始数组 `arrays.npz`。
- `layer_beta_rad.npy`、三份 `layer_*_beta_rad.txt`：三层耦合相位（弧度）；PNG 仅供预览，不能直接视作设备驱动电压。

继续训练：将 checkpoint 设成 `last.pt` 的绝对路径，epochs 改成更大的总轮数。支持恢复优化器和混合精度状态，但不保证续训后的随机批次序列与不中断训练逐位一致。验证最优权重与最后一轮权重分别保存，测试集不参与选模型。只评估时设置 mode=`test` 且 checkpoint 指向 best.pt。

可选 `--config path.json` 覆盖 CONFIG 中的同名配置，用于实验批次；未知键会报错。`--cpu` 仅用于明确要求的调试。每轮训练重新配对，验证和测试配对固定；每一对的两个原始样本索引不同（数字类别可以相同）。

## 科研含义与模型边界

1. 光场按 [L,R] 排列，严格沿用参考程序的矩阵
   `J=[[cos(g/2), -i sin(g/2) exp(+i beta)],[-i sin(g/2) exp(-i beta), cos(g/2)]]`。
   三层对两分量做相干叠加，再取模平方；不能先分别取强度再相加。
2. 该矩阵是理想等效液晶耦合模型，beta 可以解释为两倍有效指向角，不是现成 LCOS 的灰度相位查找表。三台反射式 2K73 装置是否能实现这个矩阵，需要标定反射坐标、左右旋约定、相位/偏振响应和器件间空气距离。参考 txt 的介质传播参数也不代表三台独立设备的实测间距。
3. 固定目标功率先均分给两通道，再按各图灰度分布分配能量；这对目标做了总亮度归一化，因此研究的是图像形状重建，不是绝对亮度保真。不会独立将每幅输出拉伸到最大亮度来掩盖能量损失。PSNR 的范围采用对应目标峰值，CSV 效率以单位入射功率为分母。显示 PNG 可以裁剪，但指标与原始数组不裁剪。
4. 输入 MNIST 原图是 28×28，96×96 是插值网格，不能作为原生高分辨率细节的证据。24→96 表示每个维度 4 倍采样重建，不自动证明突破衍射极限。论文还应使用原生高分辨率目标、线对/MTF、硬件标定和消融测试。
5. padding 缓解周期边界，但不替代角谱采样/窗口收敛检验。程序使用离散标量角谱与逐点 Jones 模型，不模拟全矢量 Maxwell 传播、波片/分光器误差、噪声或电压量化。
6. `--self-test` 验证形状、梯度、优化器、Jones 功率与参考符号、无损传播功率。通过自检不等于模型已训练成功；训练后的重建质量以独立测试集结果为准。
