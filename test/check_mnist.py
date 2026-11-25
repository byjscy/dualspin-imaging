# -*- coding: utf-8 -*-
"""检查原始 MNIST 压缩包，使用 Python 标准库，无需联网。"""

from pathlib import Path

MNIST_DIR = Path(r"D:\Desktop\111")
OUTPUT_DIR = Path(__file__).resolve().parent

import gzip
import hashlib
import struct
from datetime import datetime


# torchvision.datasets.MNIST.resources 定义的原版压缩包指纹。
REFERENCE = {
    "train": (60000, "f68b3c2dcbeaaa9fbdd348bbdeb94873", "d53e105ee54ea40749a09fcbcd1e9432"),
    "t10k": (10000, "9fb629c4189551a2d022fa330f9573f3", "ec29112dd5afa0611ce80d1b7f02629c"),
}
REFERENCE_URL = "https://docs.pytorch.org/vision/stable/_modules/torchvision/datasets/mnist.html"


def inspect_file(path, kind, expected_count, reference_md5):
    packed = path.read_bytes()
    checksum = hashlib.md5(packed, usedforsecurity=False).hexdigest()
    # 完整解压同时校验 gzip 的 CRC 和长度。
    payload = gzip.decompress(packed)
    if kind == "images":
        magic, count, rows, cols = struct.unpack_from(">IIII", payload)
        if (magic, rows, cols) != (2051, 28, 28) or len(payload) != 16 + count * rows * cols:
            raise ValueError("图像 IDX 头、尺寸或负载长度错误")
        details = f"{count:,} 张 {rows}×{cols} 灰度图"
    else:
        magic, count = struct.unpack_from(">II", payload)
        labels = payload[8:]
        if magic != 2049 or len(labels) != count or set(labels) != set(range(10)):
            raise ValueError("标签 IDX 头、负载长度或标签值错误")
        details = f"{count:,} 条标签，覆盖 0–9"
    if count != expected_count:
        raise ValueError(f"样本数 {count:,}，标准划分应为 {expected_count:,}")
    status = "与 torchvision 原版吻合" if checksum == reference_md5 else "与原版压缩包指纹不同"
    return f"{path.name}\n  gzip 完整，{details}。\n  MD5 {checksum}，{status}。"


def main():
    now = datetime.now().astimezone()
    result_dir = OUTPUT_DIR / now.strftime("%Y%m%d_%H%M%S_%f")
    result_dir.mkdir(parents=True)
    entries = []
    errors = []
    for split, (count, image_md5, label_md5) in REFERENCE.items():
        for kind, dimensions, md5 in (("images", 3, image_md5), ("labels", 1, label_md5)):
            path = MNIST_DIR / f"{split}-{kind}-idx{dimensions}-ubyte.gz"
            try:
                entries.append(inspect_file(path, kind, count, md5))
            except (OSError, EOFError, ValueError, struct.error) as exc:
                errors.append(f"{path.name}: {exc}")

    lines = ["MNIST 数据检查", f"时间 {now.isoformat(timespec='seconds')}", f"目录 {MNIST_DIR}", ""]
    if errors:
        lines.extend(["结论：当前数据未通过检查。", *errors])
    else:
        lines.extend([
            "结论：四个压缩包通过检查，可以直接用于 MNIST 训练和测试。",
            "训练集：60,000 张图像及对应标签。测试集：10,000 张图像及对应标签。",
            "图像原生尺寸为 28×28。后续重建程序读取 gzip 图像并转换到 96×96 目标网格。",
            f'mnist_dir = r"{MNIST_DIR}"',
        ])
    lines.extend(["", *entries, "", f"参考指纹来源 {REFERENCE_URL}"])
    report = result_dir / "mnist_check.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    print(report)
    print("MNIST check failed." if errors else "MNIST check passed.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
