# -*- coding: utf-8 -*-
"""双偏振成像，从零联合训练共享相位编码器和三层衍射系统。

默认读 Windows 上的 MNIST 文件，每次训练新建一个结果目录。训练输入是两张目标图，
编码器只输出一张 24×24 相位图。两路探测强度均由同一相位图通过三层光路计算得到。
从头训练示例：python train_dual_pol_fresh.py --epochs 120
"""

# ===================== 全局配置 =====================
CONFIG = {
    "mnist_dir": r"D:\MNIST\dataset\MNIST\raw",           # 直接读取原始 IDX.gz / IDX
    "output_dir": r"D:\srdd\dual_pol",           # 每次运行创建日期时间子目录
    "epochs": 120,                           # 全新训练的总轮数
    "wavelength_nm": 532.0,                  # 绿色激光波长，单位 nm
    "batch_size": 8,                         # 训练批量，可按显存调整
    "eval_batch_size": 16,                    # 验证和测试，无梯度可用较大批量
    "benchmark_batches": [8, 12, 16, 24, 32, 48, 64],
    "benchmark_steps": 24,                   # 每档计时批数，预热另计
    "benchmark_repeats": 3,                  # 每档使用重复测速的中位数
    "learning_rate": 0.0003,
    "seed": 42,
    "device": "cuda:0",                      # 实验室使用 srdd_gpu 环境
    "encoder_bf16": True,                    # 仅编码器用 BF16；光场为 complex64
    "train_limit": 0,                        # 0 = 使用完整的训练划分
    "val_limit": 0,                          # 只用于小规模试验；完整训练验证 5000 对
    "val_size": 5000,                        # 从官方训练集划出，其余用于训练
    "test_limit": 0,                         # 0 = 使用官方 10,000 张测试图
    "target_size": 96,
    "code_size": 24,
    "slm_size": 200,
    "padding": 100,                          # 计算网格 = slm_size + 2 * padding
    "pixel_pitch_um": 8.0,                   # 参考代码的模拟采样间隔，单位 μm
    "retardance_rad": 0.6283185307179586,     # π/5，等效模型参考值
    "active_layers": [1, 2, 3],               # 单层对照可设为 [2]，须单独重训
    # 编码面至第 1 层、层 1 至层 2、层 2 至层 3、层 3 至探测面。
    # 每段可含多个 (传播距离 m, 折射率)，数值沿用参考 txt。
    "paths": [ [[0.05, 1.0], [0.001, 1.46]], [[0.002, 1.46]],
               [[0.002, 1.46]], [[0.001, 1.46], [0.05, 1.0]] ],
    "band_limit": True,
    "target_roi_power_per_channel": 0.05,    # 每路相对于单位入射功率
    "loss": "weighted_fdmae_ssim",
    "phase_iterations": 8,                   # 每个样本先在当前光路上投影，再由网络微调相位
    "optics_learning_rate": 0.001,
    "dc_weight": 0.5,                        # FDMAE 内 DC 相对功率误差的权重
    "foreground_weight": 0.75,               # SSIM 内前景窗口平均的权重
    "min_stroke_gain": 0.02,                 # 笔画窗口 SSIM 比同一目标的全黑对照至少高此值
    "min_power_ratio": 0.5,                  # 选模时每路平均 ROI 功率应至少达到目标的这一比例
    "blank_channel_probability": 0.10,       # 沿用原 100 轮实验的空通道比例
    "val_isolation_pairs": 256,              # 固定取验证集前 256 对，两个方向分别测
    "save_examples": 24,
    "isolation_test_images": 256,
    "log_every_batches": 150,
}
# =============================================================

import argparse
import csv
import gzip
import json
import math
import struct
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from PIL import Image, ImageDraw


FORMAT_VERSION = "dual_pol_fresh_v1"
LOSS_MODES = ("weighted_fdmae_ssim", "psnr")


def validate(c):
    h, code, slm = (c[key] for key in ("target_size", "code_size", "slm_size"))
    if h < 32 or code < 1 or h % 4 or h % code or slm < h or (slm - h) % 2:
        raise ValueError("目标尺寸须为 4 和编码尺寸的整数倍，并能居中放入调制网格。")
    for key in ("epochs", "batch_size", "eval_batch_size", "val_size", "log_every_batches",
                "benchmark_steps", "benchmark_repeats"):
        if type(c[key]) is not int or c[key] < 1:
            raise ValueError(f"{key} 必须为正整数。")
    for key in ("padding", "train_limit", "val_limit", "test_limit", "isolation_test_images",
                "save_examples", "val_isolation_pairs"):
        if type(c[key]) is not int or c[key] < 0:
            raise ValueError(f"{key} 必须为非负整数。")
    if type(c["phase_iterations"]) is not int or c["phase_iterations"] < 0:
        raise ValueError("phase_iterations 需要是非负整数。")
    if not all(0 < c[k] < 1 for k in ("dc_weight", "foreground_weight")):
        raise ValueError("频域和前景权重必须位于 0 到 1 之间。")
    if not 0 < c["min_power_ratio"] <= 1 or not 0 < c["min_stroke_gain"] <= 1:
        raise ValueError("请检查选模门槛。")
    if c["blank_channel_probability"] and c["val_isolation_pairs"] < 1:
        raise ValueError("使用空通道训练时请至少验证一对隔离样本。")
    if not 2 <= c["val_size"] <= 59998 or 1 in (c["train_limit"], c["val_limit"], c["test_limit"]):
        raise ValueError("每个数据划分至少需要两张图。")
    if c["loss"] not in LOSS_MODES:
        raise ValueError(f"loss 必须是 {LOSS_MODES} 之一。")
    for key in ("wavelength_nm", "pixel_pitch_um", "learning_rate", "optics_learning_rate"):
        if not c[key] > 0:
            raise ValueError(f"{key} 必须为正数。")
    if not 0 < c["target_roi_power_per_channel"] <= 0.5 or not 0 <= c["blank_channel_probability"] < 1:
        raise ValueError("请检查目标功率或空通道概率。")
    layers = c["active_layers"]
    if not layers or layers != sorted(set(layers)) or not set(layers) <= {1, 2, 3}:
        raise ValueError("active_layers 需要按升序选择 1、2、3 中的调制面。")
    if len(c["paths"]) != 4 or any(not path for path in c["paths"]):
        raise ValueError("必须设置四段传播路径。")
    if any(z < 0 or n <= 0 for path in c["paths"] for z, n in path):
        raise ValueError("传播距离必须非负，折射率必须为正。")


def read_mnist(directory, split, device):
    root = Path(directory)

    def read(name):
        for folder in (root, root / "raw", root / "MNIST" / "raw"):
            packed = folder / (name + ".gz")
            if packed.is_file():
                return gzip.decompress(packed.read_bytes())
            plain = folder / name
            if plain.is_file():
                return plain.read_bytes()
        raise FileNotFoundError(f"{root} 缺少 {name} 或 {name}.gz。")

    pixels = read(f"{split}-images-idx3-ubyte")
    labels = read(f"{split}-labels-idx1-ubyte")
    expected = {"train": 60000, "t10k": 10000}[split]
    if len(pixels) != 16 + expected * 784 or struct.unpack_from(">IIII", pixels) != (2051, expected, 28, 28):
        raise ValueError(f"{split} 图像 IDX 文件长度或文件头异常。")
    if len(labels) != 8 + expected or struct.unpack_from(">II", labels) != (2049, expected) or max(labels[8:]) > 9:
        raise ValueError(f"{split} 标签 IDX 文件异常。")
    images = np.frombuffer(pixels, dtype=np.uint8, offset=16).copy().reshape(expected, 28, 28)
    classes = np.frombuffer(labels, dtype=np.uint8, offset=8).copy()
    # 一次上传 uint8 图像库。全量训练和测试图像共约 52 MiB。
    return torch.from_numpy(images).to(device), classes


def paired_indices(indices, seed):
    """Each digit appears once in each channel, with no identical sample pair."""
    if len(indices) < 2:
        raise ValueError("每个划分至少需要两张图。")
    order = np.random.default_rng(seed).permutation(indices)
    return np.column_stack((order, np.roll(order, 1)))


def image_batches(images, pairs, batch_size, output_size):
    indices = torch.as_tensor(pairs, device=images.device)
    for batch in indices.split(batch_size):
        x = images[batch].to(torch.float32).mul_(1 / 255)
        yield F.interpolate(x, size=(output_size, output_size), mode="bilinear", align_corners=False)


def smooth_phase(count, size, spacing):
    grid = max(2, math.ceil(size / spacing))
    coarse = torch.randn(count, 1, grid, grid)
    screen = F.interpolate(coarse, (size, size), mode="bicubic", align_corners=False)[:, 0]
    return 1.8 * screen / screen.std(dim=(-2, -1), keepdim=True).clamp_min(1e-6)


class OpticalDecoder(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.s = c["slm_size"]
        self.pad = c["padding"]
        self.grid = self.s + 2 * self.pad
        self.size = c["target_size"]
        self.offset = (self.grid - self.size) // 2
        self.code_size = c["code_size"]
        self.cell = self.size // self.code_size
        self.aperture = slice(self.pad, self.pad + self.s)
        self.roi = slice(self.offset, self.offset + self.size)
        self.active = tuple(k - 1 for k in c["active_layers"])
        screens = smooth_phase(1, self.s, 8) + 0.45 * smooth_phase(len(self.active), self.s, 8)
        self.beta = nn.ParameterDict({str(k): nn.Parameter(screen.clone()) for k, screen in zip(self.active, screens)})
        self.c = math.cos(c["retardance_rad"] / 2)
        self.sine = math.sin(c["retardance_rad"] / 2)
        transfer = self.transfer_kernels(c)
        self.first_layer = self.active[0]
        # 未启用的前置平面只有自由传播，将对应传递函数合并。
        self.register_buffer("input_transfer", transfer[:self.first_layer + 1].prod(dim=0), persistent=False)
        self.register_buffer("transfer", transfer, persistent=False)

    def transfer_kernels(self, c):
        pitch, wavelength = c["pixel_pitch_um"] * 1e-6, c["wavelength_nm"] * 1e-9
        freq = torch.fft.fftfreq(self.grid, d=pitch, dtype=torch.float64)
        fy, fx = torch.meshgrid(freq, freq, indexing="ij")
        transverse = (wavelength * fx).square() + (wavelength * fy).square()
        kernels = []
        for segments in c["paths"]:
            phase = torch.zeros_like(transverse)
            shift = torch.zeros_like(transverse)
            valid = torch.ones_like(transverse, dtype=torch.bool)
            for distance, index in segments:
                q = index**2 - transverse
                kz = q.clamp_min(0).sqrt()
                # sqrt(n²-s)-n = -s/(sqrt(n²-s)+n)，省去不影响光强的全局载波。
                phase -= (2 * math.pi * distance / wavelength) * transverse / (kz + index)
                shift += distance * wavelength / kz.clamp_min(1e-15)
                valid &= q > 0
            if c["band_limit"]:
                half_window = self.grid * pitch / 2
                valid &= ((shift * fx).abs() <= half_window) & ((shift * fy).abs() <= half_window)
            kernels.append((torch.exp(1j * phase) * valid).to(torch.complex64))
        return torch.stack(kernels)

    def apply_transfer(self, fields, transfer):
        return torch.fft.ifft2(torch.fft.fft2(fields) * transfer)

    def planes(self):
        return {k: torch.exp(1j * self.beta[str(k)]) for k in self.active}

    def field(self, cell_phasors, planes):
        # 同一块相位编码板生成两路复振幅，单位模相位编码对应单位入射功率。
        fine = cell_phasors.repeat_interleave(self.cell, -2).repeat_interleave(self.cell, -1)
        incident = F.pad(fine / self.size, (self.offset,) * 4)
        ap = self.aperture
        left = self.apply_transfer(incident, self.input_transfer)[..., ap, ap]
        first = self.first_layer
        field = F.pad(torch.stack((self.c * left, -1j * self.sine * planes[first].conj() * left), 1),
                      (self.pad,) * 4)
        for k in range(first + 1, 3):
            field = self.apply_transfer(field, self.transfer[k])
            if k in self.active:
                left, right = field[..., ap, ap].unbind(1)
                phase = planes[k]
                field = F.pad(torch.stack((self.c * left - 1j * self.sine * phase * right,
                                           self.c * right - 1j * self.sine * phase.conj() * left), 1),
                              (self.pad,) * 4)
        return self.apply_transfer(field, self.transfer[3])

    def adjoint(self, roi_field, planes):
        # ROI 光场到编码单元的共轭转置，计入有限孔径和 24→96 的块复制。
        field = F.pad(roi_field, (self.offset,) * 4)
        ap = self.aperture
        for k in range(2, self.first_layer - 1, -1):
            field = self.apply_transfer(field, self.transfer[k + 1].conj())
            if k in self.active:
                left, right = field[..., ap, ap].unbind(1)
                phase = planes[k]
                left_in = self.c * left + 1j * self.sine * phase * right
                if k == self.first_layer:
                    field = F.pad(left_in, (self.pad,) * 4)
                else:
                    right_in = self.c * right + 1j * self.sine * phase.conj() * left
                    field = F.pad(torch.stack((left_in, right_in), 1), (self.pad,) * 4)
        field = self.apply_transfer(field, self.input_transfer.conj())[..., self.roi, self.roi]
        return field.reshape(-1, self.code_size, self.cell, self.code_size, self.cell).sum((2, 4)) / self.size

    def forward(self, phase, measure_power=False):
        field = self.field(torch.exp(1j * phase), self.planes())
        intensity = field[..., self.roi, self.roi].abs().square()
        full_power = field.abs().square().sum((-2, -1)) if measure_power else None
        return intensity, full_power


class ResidualBlock(nn.Module):
    def __init__(self, width, dilation):
        super().__init__()
        self.layers = nn.Sequential(nn.GroupNorm(8, width), nn.SiLU(),
                                    nn.Conv2d(width, width, 3, padding=dilation, dilation=dilation),
                                    nn.GroupNorm(8, width), nn.SiLU(), nn.Conv2d(width, width, 3, padding=1))

    def forward(self, x):
        return x + self.layers(x)


class ImagingModel(nn.Module):
    def __init__(self, c, amp):
        super().__init__()
        self.optics = OpticalDecoder(c)
        self.amp = amp
        self.steps = c["phase_iterations"]
        self.roi_power = c["target_roi_power_per_channel"]
        # 两个独立参考相位仅用于从目标计算编码图。
        size = c["target_size"]
        self.register_buffer("reference_phasors", torch.exp(1j * smooth_phase(2, size, 8)))
        # 每次新建模型随机生成一份固定的相位扰动，供所有样本共用。
        self.register_buffer("carrier", torch.exp(4j * (torch.rand(c["code_size"], c["code_size"]) - 0.5)))
        # 入射为纯 LCP，投影计算给 RCP 的残差乘 1.25；输出强度始终使用物理尺度。
        self.register_buffer("projection_weights", torch.tensor([1., 1.25]).reshape(1, 2, 1, 1))
        width = 48
        self.encoder = nn.Sequential(
            nn.Conv2d(2 * self.optics.cell**2 + 2, width, 3, padding=1),
            *(ResidualBlock(width, dilation) for dilation in (1, 2, 4, 8)),
            nn.GroupNorm(8, width), nn.SiLU(), nn.Conv2d(width, 1, 3, padding=1))
        # 输出头初值为零，第一步采用光路求出的编码，再学习每对目标的相位修正。
        nn.init.zeros_(self.encoder[-1].weight)
        nn.init.zeros_(self.encoder[-1].bias)

    @torch.no_grad()
    def initial_code(self, x):
        # 编码阶段已知两张目标图。投影使用本批当前光路，固定初始解后再对正向成像求梯度。
        scale = self.roi_power / x.sum((-2, -1), keepdim=True).clamp_min(1e-12)
        amplitude = (x * scale).sqrt()
        optics = self.optics
        planes = optics.planes()
        cells = optics.adjoint(amplitude * self.reference_phasors * self.projection_weights, planes)
        unit = torch.exp(1j * torch.angle(cells)) * self.carrier
        previous = unit
        for _ in range(self.steps):
            wave = optics.field(unit, planes)[..., optics.roi, optics.roi]
            delta = amplitude * (wave / wave.abs().clamp_min(1e-12)) - wave
            # 按单位入射功率的归一化补偿编码单元尺度，ROI 之外的光场自由演化。
            correction = optics.adjoint(delta * self.projection_weights, planes)
            trial = unit + optics.code_size**2 * correction + 0.6 * (unit - previous)
            previous, unit = unit, torch.exp(1j * torch.angle(trial))
        return unit

    def forward(self, x, measure_power=False):
        unit = self.initial_code(x)
        features = torch.cat((F.pixel_unshuffle(x, self.optics.cell), unit.real[:, None], unit.imag[:, None]), 1)
        with torch.autocast(x.device.type, dtype=torch.bfloat16, enabled=self.amp):
            residual = self.encoder(features.contiguous(memory_format=torch.channels_last))[:, 0]
        phase = (torch.angle(unit) + math.pi * residual.float().tanh()).remainder(2 * math.pi)
        image, power = self.optics(phase, measure_power)
        return image, phase, power


def target_intensity(x, c):
    return x * (c["target_roi_power_per_channel"] / x.sum((-2, -1), keepdim=True).clamp_min(1e-8))


def image_terms(y, target, c, kernel):
    # 每对样本分别计算左右两路的损失。空目标使用同对另一通道的标尺。
    peak = target.amax((-2, -1), keepdim=True)
    floor = c["target_roi_power_per_channel"] / c["target_size"]**2
    peak = torch.where(peak > 0, peak, peak.amax(1, keepdim=True).clamp_min(floor))
    psnr, standard, stroke, black_stroke = quality_parts(y, target, peak, kernel)
    if c["loss"] == "psnr":
        objective = -psnr
    else:
        delta = y - target
        err_spec = torch.fft.fft2(delta, norm="ortho").abs()
        ref_spec = torch.fft.fft2(target, norm="ortho").abs()
        err_ac = (err_spec.sum((-2, -1)) - err_spec[..., 0, 0]).clamp_min(0)
        ref_ac = (ref_spec.sum((-2, -1)) - ref_spec[..., 0, 0]).clamp_min(0)
        # 零频分量与 ROI 总功率成正比，单独加权可使暗通道在损失中有足够影响。
        power = c["target_roi_power_per_channel"]
        present = target.sum((-2, -1)) > 0
        ref_ac = torch.where(present, ref_ac, ref_ac.amax(1, keepdim=True)).clamp_min(power / y.shape[-1])
        dc = delta.sum((-2, -1)).abs() / power
        fdmae = (1 - c["dc_weight"]) * (err_ac / ref_ac) + c["dc_weight"] * dc
        ssim = torch.lerp(standard, stroke, c["foreground_weight"])
        objective = fdmae + 1 - ssim
    return objective, psnr, standard, stroke, black_stroke


def balanced(values):
    # 两路损失的平均值占 75%，较差一路的损失占 25%。
    return 0.75 * values.mean() + 0.25 * values.max()


def epoch_loss(model, images, pairs, c, epoch, run_started, epoch_started, optimizer=None, *, log_progress=True):
    training = optimizer is not None
    model.train(training)
    totals = torch.zeros((6, 2), device=images.device, dtype=torch.float64)
    isolation_loss = torch.zeros_like(totals[0])
    isolation_count = 0
    kernel = ssim_kernel(images.device)
    batch_size = c["batch_size"] if training else c["eval_batch_size"]
    batch_count = math.ceil(len(pairs) / batch_size)
    rng = torch.Generator(device=images.device).manual_seed(c["seed"] + 3_000_000 + epoch)
    with torch.set_grad_enabled(training):
        for batch, x in enumerate(image_batches(images, pairs, batch_size, c["target_size"]), 1):
            if training and c["blank_channel_probability"]:
                half = c["blank_channel_probability"] / 2
                draw = torch.rand(len(x), device=x.device, generator=rng)
                keep = torch.stack((draw >= half, (draw < half) | (draw >= 2 * half)), dim=1)
                x = x * keep[..., None, None]
            if training:
                optimizer.zero_grad(set_to_none=True)
            y, _, _ = model(x)
            terms = image_terms(y, target_intensity(x, c), c, kernel)
            loss = balanced(terms[0].mean(0))
            if training:
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
                optimizer.step()
                totals[0] += terms[0].detach().sum(0)
            else:
                totals += torch.stack([v.sum(0) for v in (*terms, y.sum((-2, -1)))])
                count = min(len(x), c["val_isolation_pairs"] - isolation_count)
                if count > 0 and c["blank_channel_probability"]:
                    for channel in range(2):
                        single = x[:count].clone()
                        single[:, 1 - channel] = 0
                        prediction, _, _ = model(single)
                        single_terms = image_terms(prediction, target_intensity(single, c), c, kernel)
                        isolation_loss += single_terms[0].sum(0)
                    isolation_count += count
            if training and log_progress and (batch % c["log_every_batches"] == 0 or batch == batch_count):
                now = time.perf_counter()
                print(f"epoch {epoch:03d}/{c['epochs']:03d} | batch {batch:05d}/{batch_count:05d} | "
                      f"loss {loss.item():.5f} | 本轮 {format_elapsed(now - epoch_started)} | "
                      f"累计 {format_elapsed(now - run_started)}", flush=True)
    totals /= len(pairs)
    if isolation_count:
        totals[0] = torch.lerp(totals[0], isolation_loss / (2 * isolation_count), c["blank_channel_probability"])
    if not torch.isfinite(totals).all():
        raise FloatingPointError("本轮出现非有限值，请保留上一轮检查点并检查参数。")
    value = float(balanced(totals[0]))
    if training:
        return value
    names = ("objective", "psnr_db", "ssim", "stroke_ssim", "black_stroke_ssim", "roi_power")
    metrics = {f"{ch}_{name}": v for name, row in zip(names, totals.tolist()) for ch, v in zip(CHANNELS, row)}
    return value, metrics


def selection_key(val_loss, metrics, c):
    power_floor = c["min_power_ratio"] * c["target_roi_power_per_channel"]
    shortfall = 0.0
    for ch in CHANNELS:
        shortfall += max(0.0, 1 - metrics[f"{ch}_roi_power"] / power_floor)
        gain = metrics[f"{ch}_stroke_ssim"] - metrics[f"{ch}_black_stroke_ssim"]
        shortfall += max(0.0, 1 - gain / c["min_stroke_gain"])
    # 达标后按验证损失选模。全程未达标时导出缺口最小的轮次，并在报告中标明。
    return (int(shortfall > 0), shortfall, val_loss)


def save_checkpoint(state, path):
    pending = path.with_suffix(".tmp")
    torch.save(state, pending)
    pending.replace(path)


def make_optimizer(model, c, gpu):
    groups = [{"params": model.encoder.parameters(), "lr": c["learning_rate"]},
              {"params": model.optics.parameters(), "lr": c["optics_learning_rate"]}]
    return torch.optim.AdamW(groups, weight_decay=0.0, fused=gpu)


def benchmark_batches(c, device, amp):
    """Measure warmed-up training throughput on real MNIST without saving weights."""
    candidates = c["benchmark_batches"]
    if not candidates or any(type(size) is not int or size < 1 for size in candidates):
        raise ValueError("benchmark_batches 必须是正整数的列表。")
    images, _ = read_mnist(c["mnist_dir"], "train", device)
    steps = c["benchmark_steps"]
    rows = []

    def measure(size):
        torch.manual_seed(c["seed"])
        cfg = dict(c, batch_size=size)
        model = ImagingModel(cfg, amp).to(device)
        model.encoder.to(memory_format=torch.channels_last)
        optimizer = make_optimizer(model, cfg, True)
        warmup = paired_indices(np.arange(size * 4), cfg["seed"])
        pairs = paired_indices(np.arange(min(len(images), size * steps)), cfg["seed"] + 1)
        epoch_loss(model, images, warmup, cfg, 1, 0, 0, optimizer, log_progress=False)
        torch.cuda.synchronize(device)
        torch.cuda.reset_peak_memory_stats(device)
        rates = []
        for repeat in range(c["benchmark_repeats"]):
            start = time.perf_counter()
            epoch_loss(model, images, pairs, cfg, repeat + 1, 0, 0, optimizer, log_progress=False)
            torch.cuda.synchronize(device)
            rates.append(len(pairs) / (time.perf_counter() - start))
        return {"batch_size": size, "pairs_per_second": float(np.median(rates)),
                "peak_allocated_mib": torch.cuda.max_memory_allocated(device) / 2**20,
                "peak_reserved_mib": torch.cuda.max_memory_reserved(device) / 2**20, "status": "ok"}

    for size in sorted(set(candidates)):
        if size * 4 > len(images):
            raise ValueError(f"测速批量 {size} 超过可预热的样本数。")
        torch.cuda.empty_cache()
        try:
            row = measure(size)
        except torch.cuda.OutOfMemoryError:
            row = {"batch_size": size, "pairs_per_second": None, "peak_allocated_mib": None,
                   "peak_reserved_mib": None, "status": "out_of_memory"}
        rows.append(row)
        if row["status"] == "ok":
            print(f"batch {size:3d} | {row['pairs_per_second']:.1f} 对/秒 | "
                  f"PyTorch 峰值保留显存 {row['peak_reserved_mib']:.0f} MiB", flush=True)
        else:
            print(f"batch {size:3d} | 显存不足", flush=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out = Path(c["output_dir"]) / f"{stamp}_benchmark"
    out.mkdir(parents=True)
    write_csv(out / "batch_benchmark.csv", rows)
    valid = [row for row in rows if row["status"] == "ok"]
    if not valid:
        raise RuntimeError(f"选定批量均运行失败。测速记录：{out}")
    fastest = max(valid, key=lambda row: row["pairs_per_second"])
    # 多档吞吐相近时选择较小批量，避免为小幅加速减少过多更新次数。
    suggested = next(row for row in valid if row["pairs_per_second"] >= 0.95 * fastest["pairs_per_second"])
    write_json(out / "benchmark_summary.json", {"gpu": torch.cuda.get_device_name(device),
        "encoder_bf16": amp, "fft_grid": c["slm_size"] + 2 * c["padding"],
        "steps_per_repeat": steps, "repeats": c["benchmark_repeats"], "fastest": fastest,
        "suggested_batch_size": suggested["batch_size"]})
    print(f"建议 batch_size = {suggested['batch_size']}（达到最高吞吐的至少 95%）。报告：{out}", flush=True)


def main():
    run_started = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="可选 JSON 覆盖 CONFIG 的同名参数")
    parser.add_argument("--epochs", type=int, help="训练的总轮数，默认 120")
    parser.add_argument("--batch-size", type=int, help="训练批量，默认 8")
    parser.add_argument("--eval-batch-size", type=int, help="验证和测试批量，默认 16")
    parser.add_argument("--data-root", dest="mnist_dir", help="含 MNIST 原始 IDX 或 IDX.gz 的目录")
    parser.add_argument("--output-root", dest="output_dir", help="结果根目录")
    parser.add_argument("--device", help="默认 cuda:0，也可用 cpu 做小规模验证")
    parser.add_argument("--phase-iterations", type=int, help="编码时的相位投影次数，默认 8")
    parser.add_argument("--loss", choices=LOSS_MODES, help="默认为加权 FDMAE 与 SSIM，可选 psnr 做对照")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke", action="store_true", help="128 训练 / 32 验证 / 48 测试，1 轮")
    mode.add_argument("--resume", type=Path, help="仅限本版 last.pt，中断后恢复至指定总轮数")
    mode.add_argument("--test-only", type=Path, help="重新测试本版检查点的验证最优模型")
    mode.add_argument("--benchmark", action="store_true", help="在 CUDA 上比较训练批量耗时和显存")
    args = parser.parse_args()
    checkpoint = args.resume or args.test_only
    state = None
    c = dict(CONFIG)
    if checkpoint:
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if state.get("format_version") != FORMAT_VERSION:
            raise ValueError("本程序只能恢复本版检查点。要从零训练，请直接运行且省略检查点参数。")
        c.update(state["config"])
    updates = {}
    if args.config:
        updates = json.loads(args.config.read_text(encoding="utf-8-sig"))
        if not isinstance(updates, dict) or updates.keys() - c.keys():
            raise ValueError("配置文件必须为 JSON 对象，且只能覆盖 CONFIG 中已有的键。")
    for key in ("epochs", "batch_size", "eval_batch_size", "device", "mnist_dir", "output_dir", "phase_iterations", "loss"):
        if getattr(args, key) is not None:
            updates[key] = getattr(args, key)
    if state is not None:
        mutable = {"mnist_dir", "output_dir", "device", "epochs", "batch_size", "eval_batch_size",
                   "log_every_batches", "save_examples", "isolation_test_images", "test_limit"}
        changed = [k for k, v in updates.items() if k not in mutable and v != c[k]]
        if changed:
            raise ValueError(f"恢复或重测时需沿用模型与训练配置，发现变更 {changed}。")
    c.update(updates)
    if args.smoke:
        c.update(epochs=1, train_limit=128, val_limit=32, test_limit=48, save_examples=4,
                 isolation_test_images=16, val_isolation_pairs=16)
    validate(c)
    device = torch.device(c["device"])
    gpu = device.type == "cuda"
    if gpu:
        if not torch.cuda.is_available():
            raise RuntimeError("当前 Python 检测不到 CUDA，请使用安装了 GPU 版 PyTorch 的 srdd_gpu 环境。")
        torch.cuda.set_device(device)
    elif device.type == "cpu":
        torch.set_num_threads(min(torch.get_num_threads(), 4))
    else:
        raise ValueError("device 支持 cpu 或 cuda。")
    torch.manual_seed(c["seed"])
    torch.set_float32_matmul_precision("high")
    amp = bool(gpu and c["encoder_bf16"] and torch.cuda.is_bf16_supported())
    if args.benchmark:
        if not gpu:
            parser.error("--benchmark 需要 CUDA。")
        benchmark_batches(c, device, amp)
        return
    model = ImagingModel(c, amp).to(device)
    model.encoder.to(memory_format=torch.channels_last)
    optimizer = make_optimizer(model, c, gpu)
    schedule = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=7, threshold=1e-3,
        min_lr=[c["learning_rate"] / 32, c["optics_learning_rate"] / 32])
    history, start, best = [], 0, None
    smoke = args.smoke or bool(state and state["smoke"])
    if state is not None:
        best = state["best"]
        if args.resume:
            if "optimizer" not in state or "scheduler" not in state:
                raise ValueError("恢复训练请指定本版 last.pt。")
            history, start = state["history"], state["epoch"]
            if c["epochs"] <= start:
                raise ValueError(f"总轮数必须大于已完成的 {start} 轮。")
            model.load_state_dict(state["model"])
            optimizer.load_state_dict(state["optimizer"])
            schedule.load_state_dict(state["scheduler"])
        del state

    tag = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    output = Path(c["output_dir"]).resolve() / (f"{tag}_fresh" + ("_smoke" if smoke else "") +
                                              ("_test" if args.test_only else ""))
    output.mkdir(parents=True)
    write_json(output / "config.json", c)
    environment = {"gpu": torch.cuda.get_device_name(device) if gpu else "CPU", "device": str(device),
                   "cuda_runtime": torch.version.cuda if gpu else None, "pytorch": str(torch.__version__),
                   "encoder_bf16": amp, "fft_grid": model.optics.grid, "smoke": smoke,
                   "initialization": "random", "seed": c["seed"],
                   "resume_from": str(checkpoint.resolve()) if args.resume else None}
    write_json(output / "environment.json", environment)
    common = {"format_version": FORMAT_VERSION, "config": c, "smoke": smoke}
    print(f"{environment['gpu']} | {c['wavelength_nm']:g} nm | 输出 {output}", flush=True)
    training_seconds = 0.0
    if not args.test_only:
        training_started = time.perf_counter()
        images, _ = read_mnist(c["mnist_dir"], "train", device)
        order = np.random.default_rng(c["seed"]).permutation(len(images))
        val, train = order[:c["val_size"]], order[c["val_size"]:]
        train = train[:c["train_limit"] or None]
        val = val[:c["val_limit"] or None]
        val_pairs = paired_indices(val, c["seed"] + 1_000_000)
        np.savez(output / "split_indices.npz", train=train, val=val, val_pairs=val_pairs)
        if args.resume:
            save_checkpoint(dict(common, best=best), output / "best.pt")
            print(f"恢复本版第 {start} 轮的模型、优化器和学习率调度器。", flush=True)
        else:
            print(f"从随机初始化开始，第 1/{c['epochs']} 轮，随机种子 {c['seed']}。", flush=True)
        print(f"每轮训练 {len(train):,} 对，固定验证 {len(val):,} 对。", flush=True)
        for epoch in range(start + 1, c["epochs"] + 1):
            begin = time.perf_counter()
            if gpu:
                torch.cuda.reset_peak_memory_stats(device)
            train_pairs = paired_indices(train, c["seed"] + epoch)
            train_error = epoch_loss(model, images, train_pairs, c, epoch, run_started, begin, optimizer)
            val_error, metrics = epoch_loss(model, images, val_pairs, c, epoch, run_started, begin)
            rank = selection_key(val_error, metrics, c)
            lr, optics_lr = (group["lr"] for group in optimizer.param_groups)
            schedule.step(val_error)
            now = time.perf_counter()
            history.append({"epoch": epoch, "train_loss": train_error, "val_loss": val_error, **metrics,
                            "qualified": rank[0] == 0, "selection_shortfall": rank[1],
                            "encoder_lr": lr, "optics_lr": optics_lr, "seconds": now - begin,
                            "run_elapsed_seconds": now - run_started,
                            "peak_allocated_mib": torch.cuda.max_memory_allocated(device) / 2**20 if gpu else None})
            if best is None or rank < best["rank"]:
                best = {"epoch": epoch, "val_loss": val_error, "metrics": metrics, "rank": rank,
                        "model": {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}}
                save_checkpoint(dict(common, best=best), output / "best.pt")
            last = dict(common, epoch=epoch, model=model.state_dict(), optimizer=optimizer.state_dict(),
                        scheduler=schedule.state_dict(), history=history, best=best)
            save_checkpoint(last, output / "last.pt")
            write_csv(output / "history.csv", history)
            left, right = [metrics[f"{ch}_roi_power"] * 100 for ch in CHANNELS]
            ls, rs = [metrics[f"{ch}_stroke_ssim"] for ch in CHANNELS]
            print(f"epoch {epoch:03d}/{c['epochs']:03d} | train {train_error:.5f} | val {val_error:.5f} | "
                  f"验证 ROI 左 {left:.2f}% 右 {right:.2f}% | 笔画 SSIM 左 {ls:.3f} 右 {rs:.3f} | "
                  f"{'达标' if rank[0] == 0 else '未达标'} | 本轮 {format_elapsed(now - begin)}", flush=True)
        del images
        training_seconds = time.perf_counter() - training_started

    model.load_state_dict(best["model"])
    model.eval()
    test_images, labels = read_mnist(c["mnist_dir"], "t10k", device)
    subset = np.random.default_rng(c["seed"] + 2_000_000).permutation(len(test_images))
    subset = subset[:c["test_limit"] or None]
    test_pairs = paired_indices(subset, c["seed"] + 2_000_001)
    batches = image_batches(test_images, test_pairs, c["eval_batch_size"], c["target_size"])
    timing = export_results(output, model, batches, test_pairs, labels, target_intensity, c, best, environment,
                            source_checkpoint=str(checkpoint.resolve()) if args.test_only else "best.pt",
                            run_started=run_started, training_seconds=training_seconds)
    print(f"总用时 {format_elapsed(timing['total_seconds'])} | 结果已保存到 {output}", flush=True)


# 按相同强度标尺导出两路成像、串扰与线对测试。
CHANNELS = ("LCP", "RCP")


def format_elapsed(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def ssim_kernel(device):
    coeff = torch.exp(-(torch.arange(11, device=device, dtype=torch.float32) - 5).square() / 4.5)
    coeff /= coeff.sum()
    return coeff.view(1, 1, 1, 11).expand(2, 1, 1, 11).contiguous()


def quality_parts(prediction, target, peak, kernel):
    # 标准 SSIM 沿用原 11×11 高斯窗与对应目标峰值。笔画指标按窗口内目标平均亮度加权。
    p, t = prediction / peak, target / peak
    psnr = -10 * (p - t).square().mean((-2, -1)).clamp_min(1e-12).log10()
    moments = torch.cat((p, t, p.square(), t.square(), p * t), dim=0)
    horizontal = F.conv2d(moments, kernel, groups=2)
    a, b, aa, bb, ab = F.conv2d(horizontal, kernel.transpose(-1, -2).contiguous(), groups=2).chunk(5, dim=0)
    va = (aa - a.square()).clamp_min(0)
    vb = (bb - b.square()).clamp_min(0)
    cov = ab - a * b
    c1, c2 = 0.01**2, 0.03**2
    ssim = ((2 * a * b + c1) * (2 * cov + c2)) / ((a.square() + b.square() + c1) * (va + vb + c2))
    black = (c1 * c2) / ((b.square() + c1) * (vb + c2))

    def stroke_mean(values):
        weights = b.sum((-2, -1))
        return torch.where(weights > 0, (values * b).sum((-2, -1)) / weights.clamp_min(1e-12),
                           values.mean((-2, -1)))

    return psnr, ssim.mean((-2, -1)), stroke_mean(ssim), stroke_mean(black)


def gray_image(values):
    return Image.fromarray(np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8))


def save_example(folder, x, target, phase, prediction, baseline, peak, indices, labels):
    folder.mkdir(parents=True)
    np.savez_compressed(folder / "arrays.npz", targets01=x, target_intensity=target, phase_rad=phase,
                        output_intensity=prediction, baseline24=baseline, target_peak=peak,
                        mnist_index=indices, mnist_label=labels)
    items = []
    for j, name in enumerate(CHANNELS):
        for field, data in (("target", x[j]), ("output", prediction[j] / peak[j]), ("baseline", baseline[j])):
            image = gray_image(data)
            image.save(folder / f"{name}_{field}.png")
            items.append((image, f"{name} {field}"))
    code = gray_image(phase / (2 * math.pi))
    code.save(folder / "shared_phase.png")
    # 对照条的顺序与论文图 2 一致。
    ordered = [items[0], items[3], (code, "Shared phase"), items[1], items[4], items[2], items[5]]
    panel = Image.new("RGB", (7 * 148, 161), "white")
    draw = ImageDraw.Draw(panel)
    for column, (image, title) in enumerate(ordered):
        left = column * 148 + 10
        panel.paste(image.resize((128, 128), Image.Resampling.NEAREST), (left, 25))
        draw.text((left, 6), title, fill="#18252b")
    panel.save(folder / "comparison.png")


def leakage_rows(model, x, indices, mode):
    controlled = torch.zeros_like(x)
    controlled[:, mode] = x[:, mode]
    signal, _, _ = model(controlled)
    power = signal.sum(dim=(-2, -1)).cpu().numpy()
    rows = []
    for ids, values in zip(indices, power):
        desired, leak = float(values[mode]), float(values[1 - mode])
        db = 10 * math.log10(max(leak, 1e-15) / max(desired, 1e-15))
        rows.append({"target_channel": CHANNELS[mode], "mnist_index": int(ids[mode]),
                     "LCP_roi_power": float(values[0]), "RCP_roi_power": float(values[1]),
                     "desired_power": desired, "leakage_power": leak, "leakage_over_desired_db": db})
    return rows


def export_line_pairs(output, model, c, device):
    """Independent two-bar targets, one active target channel per exposure."""
    folder = output / "line_pairs"
    folder.mkdir()
    h, code_size = c["target_size"], c["code_size"]
    width = 2
    rows, profiles = [], []
    for direction in ("vertical", "horizontal"):
        for gap in (2, 4, 8):
            a = h // 2 - 1 - gap // 2
            rowslice = slice(h // 4, 3 * h // 4)
            bars = torch.zeros((h, h), device=device)
            bars[rowslice, a - width:a] = 1
            bars[rowslice, a + gap:a + gap + width] = 1
            if direction == "horizontal":
                bars = bars.T
            low = F.avg_pool2d(bars[None, None], h // code_size)[0, 0]
            low_up = F.interpolate(low[None, None], size=(h, h), mode="nearest")[0, 0]
            x = torch.eye(2, device=device)[:, :, None, None] * bars
            pred, phase, _ = model(x)
            data = pred.cpu().numpy()
            gt, low_values = bars.cpu().numpy(), low.cpu().numpy()
            samples = low_up.cpu().numpy()
            for mode, channel in enumerate(CHANNELS):
                field = data[mode, mode]
                if direction == "vertical":
                    target_profile = gt[rowslice, :].mean(axis=0)
                    baseline_profile = samples[rowslice, :].mean(axis=0)
                    output_profile = field[rowslice, :].mean(axis=0)
                else:
                    target_profile = gt[:, rowslice].mean(axis=1)
                    baseline_profile = samples[:, rowslice].mean(axis=1)
                    output_profile = field[:, rowslice].mean(axis=1)

                def contrast(profile):
                    peaks = np.r_[profile[a - width:a], profile[a + gap:a + gap + width]].mean()
                    valley = profile[a:a + gap].mean()
                    return float((peaks - valley) / max(peaks + valley, 1e-15))

                peak = max(float(field.max()), 1e-15)
                stem = f"{direction}_gap{gap}_{channel}"
                gray_image(gt).save(folder / f"{stem}_target.png")
                gray_image(low_values).save(folder / f"{stem}_baseline.png")
                gray_image(field / peak).save(folder / f"{stem}_output_preview.png")
                np.savez_compressed(folder / f"{stem}.npz", target=gt, baseline=low_values,
                                    shared_phase_rad=phase[mode].cpu().numpy(), output_intensity=data[mode])
                rows.append({"orientation": direction, "gap_samples": gap, "bar_width_samples": width,
                             "channel": channel, "output_contrast": contrast(output_profile),
                             "baseline_contrast": contrast(baseline_profile)})
                for j in range(h):
                    profiles.append({"orientation": direction, "gap_samples": gap, "channel": channel,
                                     "position_sample": j, "target_gray": float(target_profile[j]),
                                     "baseline_gray": float(baseline_profile[j]),
                                     "output_intensity": float(output_profile[j])})
    write_csv(folder / "contrast.csv", rows)
    write_csv(folder / "profiles.csv", profiles)
    return rows


@torch.inference_mode()
def export_results(output, model, batches, pairs, labels, target_intensity, c, best, environment, *,
                   source_checkpoint, run_started, training_seconds):
    device = next(model.parameters()).device
    kernel = ssim_kernel(device)
    rows, controls = [], []
    cursor = 0
    step = c["target_size"] // c["code_size"]
    metric_names = ("psnr_db", "ssim", "stroke_ssim", "black_stroke_ssim", "baseline_psnr_db", "baseline_ssim", "roi_efficiency", "full_power")
    for x in batches:
        ids = pairs[cursor:cursor + len(x)]
        truth = target_intensity(x, c)
        peak = truth.amax((-2, -1), keepdim=True).clamp_min(1e-8)
        pred, phase, power = model(x, measure_power=True)
        low = F.avg_pool2d(x, step)
        reference = F.interpolate(low, size=x.shape[-2:], mode="nearest")
        scores = torch.stack((*quality_parts(pred, truth, peak, kernel),
                              *quality_parts(target_intensity(reference, c), truth, peak, kernel)[:2],
                              pred.sum((-2, -1)), power), dim=-1).cpu().numpy()
        for i, (indices, channel_scores) in enumerate(zip(ids, scores)):
            row = {"pair": cursor + i, "idx_LCP": int(indices[0]), "idx_RCP": int(indices[1]),
                   "digit_LCP": int(labels[indices[0]]), "digit_RCP": int(labels[indices[1]])}
            for channel, values in zip(CHANNELS, channel_scores):
                row.update({f"{channel}_{metric}": float(value) for metric, value in zip(metric_names, values)})
            rows.append(row)

        n = min(len(x), max(0, c["save_examples"] - cursor))
        if n:
            arrays = [t[:n].cpu().numpy() for t in (x, truth, phase, pred, low, peak)]
            for i, values in enumerate(zip(*arrays)):
                save_example(output / "examples" / f"pair_{cursor + i:04d}", *values, ids[i], labels[ids[i]])
        n_controls = min(len(x), max(0, c["isolation_test_images"] - cursor))
        if n_controls:
            for mode in range(2):
                controls.extend(leakage_rows(model, x[:n_controls], ids[:n_controls], mode))
        cursor += len(x)

    write_csv(output / "test_metrics.csv", rows)
    write_csv(output / "crosstalk.csv", controls)
    summary = {}
    for channel in CHANNELS:
        summary[channel] = {}
        for metric in metric_names:
            values = [row[f"{channel}_{metric}"] for row in rows]
            summary[channel][metric] = {"mean": float(np.mean(values)), "std": float(np.std(values))}
        isolated = [row["leakage_over_desired_db"] for row in controls if row["target_channel"] == channel]
        if isolated:
            summary[channel]["isolation_control"] = {"count": len(isolated),
                "median_leakage_db": float(np.median(isolated)), "mean_leakage_db": float(np.mean(isolated)),
                "median_leakage_percent": float(100 * 10 ** (np.median(isolated) / 10)),
                "leakage_above_signal_count": sum(value > 0 for value in isolated)}

    phases = {}
    phase_folder = output / "layer_phases"
    phase_folder.mkdir()
    for k, param in model.optics.beta.items():
        name = f"layer_{int(k) + 1}"
        phase = param.remainder(2 * math.pi).cpu().numpy()
        phases[name] = phase
        gray_image(phase / (2 * math.pi)).save(phase_folder / f"{name}_phase_preview.png")
    np.savez_compressed(phase_folder / "effective_beta_rad.npz", **phases)
    lines_tested = export_line_pairs(output, model, c, device)
    for channel in CHANNELS:
        contrasts = [r["output_contrast"] for r in lines_tested if r["channel"] == channel]
        summary[channel]["line_pairs"] = {"positive_contrast": sum(v > 0 for v in contrasts), "tested": len(contrasts)}
    timing = {"total_seconds": time.perf_counter() - run_started, "training_seconds": training_seconds}
    write_json(output / "test_summary.json", {"pairs": len(rows), "selected_epoch": best["epoch"],
        "best_val_loss": best["val_loss"], "source_checkpoint": source_checkpoint, "smoke": environment["smoke"],
        "wavelength_nm": c["wavelength_nm"], "active_layers": c["active_layers"], "channels": summary,
        "training_pairs_per_epoch": min(60000 - c["val_size"], c["train_limit"] or 60000),
        "validation_pairs": min(c["val_size"], c["val_limit"] or c["val_size"]),
        "timing": timing, "trained_loss": c["loss"], "initialization": "random", "resume_from": environment["resume_from"],
        "selection_qualified": best["rank"][0] == 0, "selected_val_metrics": best["metrics"],
        "interpretation": "Ideal Jones angular-spectrum simulation. Efficiency is ROI power per unit incident power."})
    selection = ("两路达到验证选模门槛，按验证损失选择" if best["rank"][0] == 0 else
                 "没有轮次同时达到两路门槛，输出验证缺口最小的一轮")
    loss_label = {"weighted_fdmae_ssim": "加权 FDMAE + (1 − 加权 SSIM)", "psnr": "负 PSNR"}[c["loss"]]
    lines = ["双通道偏振成像运行结论", f"运行模式 {'短程功能验证' if environment['smoke'] else '配置训练或测试'}",
             f"训练损失 {loss_label}，训练起点为随机初始化。",
             f"设备 {environment['gpu']}，波长 {c['wavelength_nm']:g} nm，调制层 {c['active_layers']}",
             f"{selection}，选中第 {best['epoch']} 轮，使用 {len(rows):,} 对独立测试集样本。",
             f"每个点亮通道的目标 ROI 功率为入射功率的 {100*c['target_roi_power_per_channel']:g}%。",
             f"选模门槛为每路平均 ROI 效率至少 {100*c['target_roi_power_per_channel']*c['min_power_ratio']:g}%，"
             f"且每路笔画 SSIM 超过全黑对照至少 {c['min_stroke_gain']:g}。",
             f"训练与验证用时 {format_elapsed(timing['training_seconds'])}。", ""]
    for channel in CHANNELS:
        stats = summary[channel]
        lines.append(f"{channel} 平均 PSNR {stats['psnr_db']['mean']:.3f} dB，"
                     f"SSIM {stats['ssim']['mean']:.4f}，ROI 效率 {100 * stats['roi_efficiency']['mean']:.3f}%。")
        lines.append(f"笔画加权 SSIM {stats['stroke_ssim']['mean']:.4f}，"
                     f"同一目标的全黑对照 {stats['black_stroke_ssim']['mean']:.4f}。"
                     f"线对正对比 {stats['line_pairs']['positive_contrast']}/{stats['line_pairs']['tested']}。")
        if "isolation_control" in stats:
            control = stats["isolation_control"]
            lines.append(f"仅指定 {channel} 成像时，漏光比例中位数 {control['median_leakage_percent']:.1f}%，"
                         f"其中 {control['leakage_above_signal_count']}/{control['count']} 组漏光功率超过目标通道。")
    if environment["smoke"]:
        lines.append("短程试跑因此处样本与轮数有限，仅验证程序和数据导出流程。")
    lines.extend(["",
        "PSNR 和 SSIM 采用各目标峰值定义动态范围，强度图未经逐图拉伸。",
        "线对输出为训练集外目标的仿真响应。线对 PNG 仅用于预览，强度与剖面以数组和 CSV 为准。",
        "有效 Jones 模型和 FFT 窗口需按器件标定及会聚性测试确认。96×96 输出尺寸表示采样网格。"])
    (output / "result_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return timing


if __name__ == "__main__":
    main()
