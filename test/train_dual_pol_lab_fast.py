# -*- coding: utf-8 -*-
"""Lab computer copy with the result export functions bundled for one-file upload."""

# ===================== 全局配置 =====================
CONFIG = {
    "mnist_dir": r"D:\MNIST\dataset\MNIST\raw",           # 直接读取原始 IDX.gz / IDX
    "output_dir": r"D:\srdd\dual_pol",           # 每次运行创建日期时间子目录
    "epochs": 100,                            # 训练总轮数
    "wavelength_nm": 532.0,                  # 绿色激光波长，单位 nm
    "batch_size": 12,                         # 训练；按 RTX 5070 的 --benchmark 结果调整
    "eval_batch_size": 64,                    # 验证和测试，无梯度可用较大批量
    "benchmark_batches": [8, 12, 16, 24, 32, 48, 64],
    "benchmark_steps": 24,                   # 每档计时批数，预热另计
    "benchmark_repeats": 3,                  # 每档使用重复测速的中位数
    "learning_rate": 0.001,
    "seed": 42,
    "device": "cuda:0",                      # 实验室使用 srdd_gpu 环境
    "encoder_bf16": True,                    # 仅编码器用 BF16；光场为 complex64
    "train_limit": 0,                        # 0 = 使用完整的训练划分
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
    "edge_loss_weight": 0.05,
    "blank_channel_probability": 0.10,       # 部分训练对只保留一个目标，优化隔离度
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


MODEL_KEYS = ("target_size", "code_size", "slm_size", "padding", "pixel_pitch_um",
              "wavelength_nm", "retardance_rad", "active_layers", "paths", "band_limit")


def validate(c):
    h, code, slm = (c[key] for key in ("target_size", "code_size", "slm_size"))
    if h < 32 or code < 1 or h % 4 or h % code or slm < h or (slm - h) % 2:
        raise ValueError("目标尺寸须为 4 和编码尺寸的整数倍，并能居中放入调制网格。")
    for key in ("epochs", "batch_size", "eval_batch_size", "val_size", "log_every_batches",
                "benchmark_steps", "benchmark_repeats"):
        if c[key] < 1:
            raise ValueError(f"{key} 必须为正整数。")
    for key in ("padding", "train_limit", "test_limit", "isolation_test_images", "save_examples", "edge_loss_weight"):
        if c[key] < 0:
            raise ValueError(f"{key} 不能为负。")
    for key in ("wavelength_nm", "pixel_pitch_um", "learning_rate"):
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


class OpticalDecoder(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.s = c["slm_size"]
        self.pad = c["padding"]
        self.grid = self.s + 2 * self.pad
        self.size = c["target_size"]
        self.offset = (self.grid - self.size) // 2
        self.active = tuple(k - 1 for k in c["active_layers"])
        self.beta = nn.ParameterDict({str(k): nn.Parameter(0.1 * torch.randn(self.s, self.s)) for k in self.active})
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

    def propagate(self, field, segment):
        return torch.fft.ifft2(torch.fft.fft2(field) * self.transfer[segment])

    def forward(self, code, measure_power=False):
        # 用一份相位图照明，入口为单位功率的纯 LCP。第一次 FFT 仅计算标量场。
        fine = F.interpolate(code, size=(self.size, self.size), mode="nearest")[:, 0]
        incident = F.pad(torch.exp(1j * fine) / self.size, (self.offset,) * 4)
        aperture = slice(self.pad, self.pad + self.s)
        # 第一块有效调制层的入射只有 LCP，直接计算 Jones 矩阵的第一列。
        left = torch.fft.ifft2(torch.fft.fft2(incident) * self.input_transfer)[..., aperture, aperture]
        phase = torch.exp(1j * self.beta[str(self.first_layer)])
        field = F.pad(torch.stack((self.c * left, -1j * self.sine * phase.conj() * left), dim=1), (self.pad,) * 4)
        field = self.propagate(field, self.first_layer + 1)
        for k in range(self.first_layer + 1, 3):
            if k in self.active:
                left, right = field[..., aperture, aperture].unbind(1)
                phase = torch.exp(1j * self.beta[str(k)])
                # [L,R] 与参考 txt 一致：R->L 使用 +β，L->R 使用 −β。
                left_out = self.c * left - 1j * self.sine * phase * right
                right_out = self.c * right - 1j * self.sine * phase.conj() * left
                field = F.pad(torch.stack((left_out, right_out), dim=1), (self.pad,) * 4)
            field = self.propagate(field, k + 1)
        roi = slice(self.offset, self.offset + self.size)
        intensity = field[..., roi, roi].abs().square()
        full_power = field.abs().square().sum(dim=(-2, -1)) if measure_power else None
        return intensity, full_power


class ImagingModel(nn.Module):
    def __init__(self, c, amp):
        super().__init__()
        self.optics = OpticalDecoder(c)
        self.code_size = c["code_size"]
        self.amp = amp
        self.encoder = nn.Sequential(
            nn.Conv2d(2, 24, 4, stride=2, padding=1), nn.GELU(),
            nn.Conv2d(24, 48, 4, stride=2, padding=1), nn.GELU(),
            nn.Conv2d(48, 48, 3, padding=1), nn.GELU(),
            nn.Conv2d(48, 1, 3, padding=1),
        )

    def forward(self, x, measure_power=False):
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=self.amp):
            logits = self.encoder(x.contiguous(memory_format=torch.channels_last))
        logits = logits.float()
        if logits.shape[-1] != self.code_size:
            logits = F.adaptive_avg_pool2d(logits, (self.code_size, self.code_size))
        code = (2 * math.pi) * logits.sigmoid()
        image, power = self.optics(code, measure_power)
        return image, code[:, 0], power


def target_intensity(x, c):
    return x * (c["target_roi_power_per_channel"] / x.sum((-2, -1), keepdim=True).clamp_min(1e-8))


def image_loss(y, target, c):
    error = (y - target) * (c["target_size"]**2 / (2 * c["target_roi_power_per_channel"]))
    mse = error.square().mean()
    edge_x = error.diff(dim=-1).abs().mean()
    edge_y = error.diff(dim=-2).abs().mean()
    return mse + c["edge_loss_weight"] * (edge_x + edge_y)


def epoch_loss(model, images, pairs, c, epoch, run_started, epoch_started, optimizer=None, *, log_progress=True):
    training = optimizer is not None
    model.train(training)
    total = torch.zeros((), device=images.device)
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
            loss = image_loss(y, target_intensity(x, c), c)
            if training:
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            total += loss.detach() * len(x)
            if training and log_progress and (batch % c["log_every_batches"] == 0 or batch == batch_count):
                current_loss = loss.item()  # 等待该批次的 CUDA 计算，再读时间。
                now = time.perf_counter()
                print(f"epoch {epoch:03d}/{c['epochs']:03d} | batch {batch:05d}/{batch_count:05d} | "
                      f"loss {current_loss:.5f} | 本轮 {format_elapsed(now - epoch_started)} | "
                      f"累计 {format_elapsed(now - run_started)}", flush=True)
    value = total.item() / len(pairs)
    if not math.isfinite(value):
        raise FloatingPointError("发现非有限损失，请降低学习率或关闭 encoder_bf16 后检查。")
    return value


def save_checkpoint(state, path):
    pending = path.with_suffix(".tmp")
    torch.save(state, pending)
    pending.replace(path)


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
        optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["learning_rate"], fused=True, weight_decay=0.0)
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
    parser.add_argument("--smoke", action="store_true", help="128 训练 / 32 验证 / 48 测试，运行 1 轮")
    parser.add_argument("--config", type=Path, help="可选 JSON 文件覆盖 CONFIG 中的同名参数")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--resume", type=Path, help="从本程序的 last.pt 继续训练至配置中的总轮数")
    mode.add_argument("--test-only", type=Path, help="用本程序的 best.pt 或 last.pt 中的验证最优权重重新测试")
    mode.add_argument("--benchmark", action="store_true", help="用 MNIST 测训练批量吞吐，生成测速报告")
    args = parser.parse_args()
    c = dict(CONFIG)
    if args.config:
        updates = json.loads(args.config.read_text(encoding="utf-8-sig"))
        if not isinstance(updates, dict) or updates.keys() - c.keys():
            raise ValueError("配置文件必须为 JSON 对象，且只能覆盖 CONFIG 中已有的键。")
        c.update(updates)
    if args.smoke:
        if args.resume or args.test_only or args.benchmark:
            parser.error("--smoke 只用于全新短程试跑。")
        c.update(epochs=1, train_limit=128, val_size=32, test_limit=48,
                 save_examples=4, isolation_test_images=16)
    validate(c)
    device = torch.device(c["device"])
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("请用已有的 srdd_gpu 环境运行。该程序需要可用的 NVIDIA CUDA。")
    torch.cuda.set_device(device)
    torch.manual_seed(c["seed"])
    torch.set_float32_matmul_precision("high")
    amp = c["encoder_bf16"] and torch.cuda.is_bf16_supported()
    if args.benchmark:
        print(f"{torch.cuda.get_device_name(device)} | CUDA {torch.version.cuda} | 批量测速", flush=True)
        benchmark_batches(c, device, amp)
        return
    model = ImagingModel(c, amp).to(device)
    model.encoder.to(memory_format=torch.channels_last)
    optimizer = torch.optim.AdamW(model.parameters(), lr=c["learning_rate"], fused=True, weight_decay=0.0)

    history, start, best = [], 0, None
    smoke_origin = args.smoke
    checkpoint_path = args.resume or args.test_only
    if checkpoint_path:
        state = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        smoke_origin = bool(state.get("smoke", checkpoint_path.parent.name.endswith("_smoke")))
        locked = MODEL_KEYS + ("target_roi_power_per_channel",)
        if args.resume:
            locked += ("seed", "train_limit", "val_size", "blank_channel_probability", "edge_loss_weight")
        for key in locked:
            if state["config"][key] != c[key]:
                raise ValueError(f"配置 {key} 与检查点不一致。")
        best = state["best"]
        if args.resume:
            if "optimizer" not in state:
                raise ValueError("续训需要 last.pt。")
            history, start = state["history"], state["epoch"]
            for row in history:
                row.setdefault("peak_allocated_mib", None)
                row.setdefault("run_elapsed_seconds", None)
            if c["epochs"] <= start:
                raise ValueError(f"续训时 epochs 必须大于已完成的 {start}。")
            model.load_state_dict(state["model"])
            optimizer.load_state_dict(state["optimizer"])
            if c["batch_size"] != state["config"]["batch_size"]:
                print(f"续训批量从 {state['config']['batch_size']} 改为 {c['batch_size']}，每轮优化器更新次数会变化。", flush=True)
            for group in optimizer.param_groups:
                group["lr"] = c["learning_rate"]

    tag = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    output = Path(c["output_dir"]).resolve() / f"{tag}{'_smoke' if smoke_origin else ''}"
    output.mkdir(parents=True)
    write_json(output / "config.json", c)
    environment = {"gpu": torch.cuda.get_device_name(device), "cuda_runtime": torch.version.cuda,
                   "pytorch": str(torch.__version__), "encoder_bf16": amp,
                   "fft_grid": model.optics.grid, "smoke": smoke_origin}
    write_json(output / "environment.json", environment)
    print(f"{environment['gpu']} | CUDA {torch.version.cuda} | {c['wavelength_nm']:g} nm | {output}", flush=True)
    training_seconds = 0.0
    if not args.test_only:
        training_started = time.perf_counter()
        train_images, _ = read_mnist(c["mnist_dir"], "train", device)
        order = np.random.default_rng(c["seed"]).permutation(len(train_images))
        val_indices, train_indices = order[:c["val_size"]], order[c["val_size"]:]
        if c["train_limit"]:
            train_indices = train_indices[:c["train_limit"]]
        val_pairs = paired_indices(val_indices, c["seed"] + 1_000_000)
        np.savez(output / "split_indices.npz", train=train_indices, val=val_indices, val_pairs=val_pairs)
        for epoch in range(start + 1, c["epochs"] + 1):
            begin = time.perf_counter()
            torch.cuda.reset_peak_memory_stats(device)
            train_pairs = paired_indices(train_indices, c["seed"] + epoch)
            train_error = epoch_loss(model, train_images, train_pairs, c, epoch, run_started, begin, optimizer)
            val_error = epoch_loss(model, train_images, val_pairs, c, epoch, run_started, begin)
            now = time.perf_counter()
            seconds = now - begin
            history.append({"epoch": epoch, "train_loss": train_error, "val_loss": val_error, "seconds": seconds,
                            "peak_allocated_mib": torch.cuda.max_memory_allocated(device) / 2**20,
                            "run_elapsed_seconds": now - run_started})
            improved = best is None or val_error < best["val_loss"]
            if improved:
                best = {"epoch": epoch, "val_loss": val_error,
                        "model": {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}}
            last = {"epoch": epoch, "config": c, "model": model.state_dict(), "optimizer": optimizer.state_dict(),
                    "history": history, "best": best, "smoke": smoke_origin}
            save_checkpoint(last, output / "last.pt")
            write_csv(output / "history.csv", history)
            print(f"epoch {epoch:03d}/{c['epochs']:03d} 完成 | train {train_error:.5f} | val {val_error:.5f} | "
                  f"本轮 {format_elapsed(seconds)} | 累计 {format_elapsed(now - run_started)}", flush=True)
        save_checkpoint({"best": best, "config": c, "smoke": smoke_origin}, output / "best.pt")
        del train_images
        training_seconds = time.perf_counter() - training_started

    model.load_state_dict(best["model"])
    model.eval()
    test_images, labels = read_mnist(c["mnist_dir"], "t10k", device)
    # 限量测试采用固定随机子集，完整测试使用全部官方测试集。
    subset = np.random.default_rng(c["seed"] + 2_000_000).permutation(len(test_images))
    if c["test_limit"]:
        subset = subset[:c["test_limit"]]
    test_pairs = paired_indices(subset, c["seed"] + 2_000_001)
    batches = image_batches(test_images, test_pairs, c["eval_batch_size"], c["target_size"])
    timing = export_results(output, model, batches, test_pairs, labels, target_intensity, c, best, environment,
                            source_checkpoint=str(checkpoint_path) if args.test_only else "best.pt",
                            run_started=run_started, training_seconds=training_seconds)
    print(f"总用时 {format_elapsed(timing['total_seconds'])} | "
          f"训练与验证 {format_elapsed(timing['training_seconds'])}", flush=True)
    print(f"结果已保存到 {output}", flush=True)


# Result export code bundled from export_results.py for one-file upload.
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


def quality(prediction, target, peak, kernel):
    # 两路分别以对应目标峰值为 data range，预测值不单独拉伸或裁剪。
    p, t = prediction / peak, target / peak
    mse = (p - t).square().mean(dim=(-2, -1))
    psnr = -10 * mse.clamp_min(1e-12).log10()
    # 相同的 11×11 可分离高斯窗，批量滤波五个矩以减少计算。
    moments = torch.cat((p, t, p.square(), t.square(), p * t), dim=0)
    horizontal = F.conv2d(moments, kernel, groups=2)
    a, b, aa, bb, ab = F.conv2d(horizontal, kernel.transpose(-1, -2).contiguous(), groups=2).chunk(5, dim=0)
    va = (aa - a.square()).clamp_min(0)
    vb = (bb - b.square()).clamp_min(0)
    cov = ab - a * b
    ssim = ((2 * a * b + 0.01**2) * (2 * cov + 0.03**2)) / (
        (a.square() + b.square() + 0.01**2) * (va + vb + 0.03**2)
    )
    return psnr, ssim.mean(dim=(-2, -1))


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


@torch.inference_mode()
def export_results(output, model, batches, pairs, labels, target_intensity, c, best, environment, *,
                   source_checkpoint, run_started, training_seconds):
    device = next(model.parameters()).device
    coeff = torch.exp(-(torch.arange(11, device=device, dtype=torch.float32) - 5).square() / 4.5)
    coeff /= coeff.sum()
    kernel = coeff.view(1, 1, 1, 11).expand(2, 1, 1, 11).contiguous()
    rows, controls = [], []
    cursor = 0
    step = c["target_size"] // c["code_size"]
    metric_names = ("psnr_db", "ssim", "baseline_psnr_db", "baseline_ssim", "roi_efficiency", "full_power")
    for x in batches:
        ids = pairs[cursor:cursor + len(x)]
        truth = target_intensity(x, c)
        peak = truth.amax((-2, -1), keepdim=True).clamp_min(1e-8)
        pred, phase, power = model(x, measure_power=True)
        low = F.avg_pool2d(x, step)
        reference = F.interpolate(low, size=x.shape[-2:], mode="nearest")
        scores = torch.stack((*quality(pred, truth, peak, kernel),
                              *quality(target_intensity(reference, c), truth, peak, kernel),
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
                "median_leakage_db": float(np.median(isolated)), "mean_leakage_db": float(np.mean(isolated))}

    phases = {}
    phase_folder = output / "layer_phases"
    phase_folder.mkdir()
    for k, param in model.optics.beta.items():
        name = f"layer_{int(k) + 1}"
        phase = param.remainder(2 * math.pi).cpu().numpy()
        phases[name] = phase
        gray_image(phase / (2 * math.pi)).save(phase_folder / f"{name}_phase_preview.png")
    np.savez_compressed(phase_folder / "effective_beta_rad.npz", **phases)
    export_line_pairs(output, model, c, device)
    timing = {"total_seconds": time.perf_counter() - run_started, "training_seconds": training_seconds}
    write_json(output / "test_summary.json", {"pairs": len(rows), "selected_epoch": best["epoch"],
        "best_val_loss": best["val_loss"], "source_checkpoint": source_checkpoint, "smoke": environment["smoke"],
        "wavelength_nm": c["wavelength_nm"], "active_layers": c["active_layers"], "channels": summary,
        "timing": timing,
        "interpretation": "Ideal Jones angular-spectrum simulation. Efficiency is ROI power per unit incident power."})
    lines = ["双通道偏振成像运行结论", f"运行模式 {'短程功能验证' if environment['smoke'] else '配置训练或测试'}",
             f"设备 {environment['gpu']}，CUDA {environment['cuda_runtime']}",
             f"波长 {c['wavelength_nm']:g} nm，调制层 {c['active_layers']}",
             f"按验证损失选中第 {best['epoch']} 轮，使用 {len(rows):,} 对独立测试集样本。",
             f"本次运行总用时 {format_elapsed(timing['total_seconds'])}（含准备、训练、测试和结果导出）。",
             f"本次训练与验证用时 {format_elapsed(timing['training_seconds'])}。", ""]
    for channel in CHANNELS:
        stats = summary[channel]
        lines.append(f"{channel} 平均 PSNR {stats['psnr_db']['mean']:.3f} dB，"
                     f"SSIM {stats['ssim']['mean']:.4f}，ROI 效率 {100 * stats['roi_efficiency']['mean']:.3f}%。")
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
