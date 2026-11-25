# 双旋衍射成像 · DualSpin Imaging

双旋衍射成像是一个双圆偏振通道的计算成像仿真项目。程序将两张 96×96 目标图编码为同一张 24×24 相位图，通过三层等效 Jones 偏振调制和自由空间传播，在左旋和右旋圆偏振通道分别重建图像。Blender 场景用于展示设备布局与反射光路。输出的 96×96 是仿真采样网格，实际光学分辨率需要通过线对实验和器件标定确认。

## 本机运行环境

以下版本来自 Windows 上实际运行的 Conda `DP` 环境。

| 组件 | 本机配置 |
| --- | --- |
| Python | 3.9.25，64 位 |
| PyTorch | 2.7.1+cu118 |
| CUDA 运行时 | 11.8，由 PyTorch CUDA wheel 提供 |
| NVIDIA 显卡 | GeForce RTX 4060 Laptop GPU，约 8 GB 显存 |
| NVIDIA 驱动 | 617.14 |
| NumPy | 2.0.1 |
| Pillow | 11.1.0 |

使用预编译的 PyTorch wheel 运行训练需要兼容的 NVIDIA 驱动，无需单独安装 CUDA Toolkit 或 `nvcc`。基础版默认使用 `cuda:0`。支持 BF16 的显卡会为编码器启用 BF16，复数光场使用 complex64。显存不足时可在配置中减小 `batch_size`。

## 安装和试跑

在 Windows PowerShell 中执行以下命令。已有同版本 `DP` 环境时，可直接激活并检查 CUDA。

```powershell
git clone https://github.com/byjscy/dualspin-imaging.git
cd dualspin-imaging
conda create -n DP python=3.9.25 -y
conda activate DP
python -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu118
python -m pip install numpy==2.0.1 Pillow==11.1.0
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

检查命令应输出 `2.7.1+cu118 11.8 True`。其他发行版本可查阅 [PyTorch 官方安装说明](https://pytorch.org/get-started/previous-versions/#v271)。

准备 [MNIST](https://yann.lecun.org/exdb/mnist/) 的四个原始 IDX 文件，集中放在同一目录。程序同时支持以下文件的解压版本。

- `train-images-idx3-ubyte.gz`
- `train-labels-idx1-ubyte.gz`
- `t10k-images-idx3-ubyte.gz`
- `t10k-labels-idx1-ubyte.gz`

在仓库根目录创建 `config.local.json`，将 `mnist_dir` 改为实际的数据目录。下面用正斜杠表示 Windows 路径。

```json
{
  "mnist_dir": "D:/data/MNIST",
  "output_dir": "test",
  "batch_size": 8
}
```

```powershell
# 用少量数据训练 1 轮并导出结果
python test/train_dual_pol.py --config config.local.json --smoke

# 按配置正式训练和测试，可在 JSON 中设置 epochs
python test/train_dual_pol.py --config config.local.json
```

如果用 Miniconda 默认路径安装了 `DP`，也可通过 `.\test\run_cuda.cmd --config config.local.json --smoke` 启动基础版。详见 [运行说明](test/运行说明.txt)。

每次运行会创建带时间戳的输出目录。主要文件包括 `best.pt`、`last.pt`、`history.csv`、`test_summary.json`，以及重建样图、调制相位、串扰和线对测试结果。基础版支持通过 `--resume` 续训，或通过 `--test-only` 重新评估同版本的检查点。

## 程序入口

| 入口 | 用途 |
| --- | --- |
| [train_dual_pol.py](test/train_dual_pol.py) | 基础训练与评估，调用独立的结果导出模块。 |
| [train_dual_pol_lab.py](test/train_dual_pol_lab.py)、[train_dual_pol_lab_fast.py](test/train_dual_pol_lab_fast.py) | 实验室单文件版，后者支持 CUDA 批量吞吐测试。 |
| [train_dual_pol_improved.py](test/train_dual_pol_improved.py)、[train_dual_pol_fdmae.py](test/train_dual_pol_fdmae.py) | 可从已有权重开始微调，FDMAE 版默认使用 FDMAE 与 SSIM 损失。 |
| [train_dual_pol_fresh.py](test/train_dual_pol_fresh.py) | 从零联合训练共享相位编码器和三层衍射系统。 |
| [dual_sr.py](code/dual_sr.py)、[polar_sr_cuda.py](code/polar_sr_cuda.py) | 独立仿真实现，分别参见 [dual_sr 说明](code/dual_sr_README.md) 和 [CUDA 仿真说明](code/polar_sr_cuda_README.md)。 |
| [Blender 建模说明](code/README.md) | 查看 `models/` 中的光路模型或重新渲染时使用 Blender。 |
