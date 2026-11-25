# -*- coding: utf-8 -*-
"""Export reproducible figure data for the two circular polarization channels."""

import csv
import json
import math
import time

import numpy as np
from PIL import Image, ImageDraw
import torch
from torch.nn import functional as F


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
    def blur(x):
        return F.conv2d(x, kernel, groups=2)
    a, b = blur(p), blur(t)
    va = (blur(p.square()) - a.square()).clamp_min(0)
    vb = (blur(t.square()) - b.square()).clamp_min(0)
    cov = blur(p * t) - a * b
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
    kernel = (coeff[:, None] * coeff).expand(2, 1, 11, 11).contiguous()
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
