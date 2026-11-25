# -*- coding: utf-8 -*-
"""Windows / CUDA: two images -> one phase code -> three Jones layers.

Effective research simulation, not a calibrated commercial LCOS model.
Run: python polar_sr_cuda.py; quick check: python polar_sr_cuda.py --self-test
"""

# ==================== 全局配置：首先修改这里 ====================
CONFIG = {
    "mnist_dir": r"D:\datasets\MNIST",  # 支持原始 IDX / IDX.gz，递归查找
    "output_dir": r"D:\srdd\output\polar_sr",
    "download_mnist": False,             # True：从 MNIST 官方镜像下载
    "epochs": 80,
    "batch_size": 8,                     # 显存不足时改为 4 或 2
    "learning_rate": 0.001,
    "num_workers": 0,                    # Windows 默认 0，稳定；可改 2
    "seed": 42,
    "device": "cuda",                   # 无 CUDA 时明确报错；调试可设 cpu
    "cuda_index": 0,
    "amp_encoder": True,                # 仅电子编码器混合精度，光学保持 complex64
    "train_limit": 0,                    # 0：全部训练数据；调试可用 256
    "val_size": 5000,                    # 从官方训练集独立划分，不使用测试集选模型
    "test_limit": 0,                     # 0：官方完整测试集
    "target_size": 96,
    "code_size": 24,
    "slm_size": 200,                     # 三层液晶有效采样网格
    "padding": 100,                      # FFT 边界扩展，需做收敛性检查
    "pixel_pitch_m": 8e-6,               # 光学计算平面采样间隔；非厂商规格确认
    "wavelength_m": 532e-9,              # 绿色激光 532 nm；520 nm 请改 520e-9
    "retardance_rad": 0.6283185307179586, # gamma=pi/5，沿用参考程序；三层固定延迟
    # 四段：编码面->层1、层1->层2、层2->层3、层3->探测面。
    # 每段为 [(传播距离 m, 折射率)]，保留参考程序的空气/介质分段。
    "segments": [[(0.05, 1.0), (0.001, 1.46)], [(0.002, 1.46)],
                 [(0.002, 1.46)], [(0.001, 1.46), (0.05, 1.0)]],
    "target_total_power": 0.10,           # 两通道目标 ROI 合计占入射功率，均分
    "gradient_loss_weight": 0.05,
    "grad_clip": 1.0,
    "save_examples": 8,
    "checkpoint": "",                   # 本程序生成的 last.pt / best.pt
    "mode": "train",                    # train / test；test 必须指定 checkpoint
}
# ==============================================================

import argparse
import csv
import gzip
import json
import math
import random
import struct
import time
import urllib.request
from datetime import datetime
from pathlib import Path
import multiprocessing

try:
    import numpy as np
    from PIL import Image, ImageDraw
    import torch
    from torch import nn
    from torch.nn import functional as F
    from torch.utils.data import Dataset, DataLoader
except ImportError as exc:
    raise SystemExit(f"缺少依赖：{exc}。请参考 polar_sr_cuda_README.md 安装 CUDA 版 PyTorch。")


def validate(c):
    for key in ("epochs", "batch_size", "target_size", "code_size", "slm_size", "val_size"):
        if c[key] < 1:
            raise ValueError(key + " 必须大于 0")
    if c["target_size"] % c["code_size"] or c["target_size"] % 4:
        raise ValueError("target_size 必须是 code_size 和 4 的整数倍")
    if c["slm_size"] < c["target_size"] or (c["slm_size"]-c["target_size"]) % 2:
        raise ValueError("slm_size 必须不小于 target_size，且尺寸差为偶数")
    if c["padding"] < 0 or c["num_workers"] < 0:
        raise ValueError("padding / num_workers 不能为负数")
    if any(c[key]<0 for key in ("train_limit","test_limit","save_examples","gradient_loss_weight")) or c["grad_clip"]<=0:
        raise ValueError("数量与损失权重不能为负，grad_clip 必须为正")
    if not 0 < c["target_total_power"] <= 1:
        raise ValueError("target_total_power 必须位于 (0,1]")
    if c["wavelength_m"] <= 0 or c["pixel_pitch_m"] <= 0 or c["learning_rate"] <= 0:
        raise ValueError("波长、采样间隔、学习率必须为正数")
    if len(c["segments"]) != 4 or any(not seg for seg in c["segments"]):
        raise ValueError("必须指定四段非空传播路径")
    if any(z < 0 or n <= 0 for seg in c["segments"] for z, n in seg):
        raise ValueError("传播距离不能为负，折射率必须为正")
    if c["mode"] not in ("train", "test"):
        raise ValueError("mode 必须为 train 或 test")


def read_mnist(root, train, download):
    """Direct IDX reader; accepts flat folders and MNIST/raw, gz or extracted."""
    root = Path(root)
    prefix = "train" if train else "t10k"
    name = prefix + "-images-idx3-ubyte"
    matches = sorted(root.rglob(name)) if root.exists() else []
    if not matches:
        matches = sorted(root.rglob(name + ".gz")) if root.exists() else []
    if not matches and download:
        root.mkdir(parents=True, exist_ok=True)
        dest = root / (name + ".gz")
        temporary = root / (name + ".download")
        urllib.request.urlretrieve("https://ossci-datasets.s3.amazonaws.com/mnist/" + name + ".gz", temporary)
        temporary.replace(dest)
        matches = [dest]
    if not matches:
        raise FileNotFoundError(f"{root} 中找不到 {name} 或 {name}.gz；检查全局配置。")
    p = matches[0]
    payload = gzip.open(p, "rb").read() if p.suffix == ".gz" else p.read_bytes()
    if len(payload) < 16:
        raise ValueError(f"IDX 文件不完整：{p}")
    magic, count, h, w = struct.unpack(">IIII", payload[:16])
    if magic != 2051 or h != 28 or w != 28 or len(payload) != 16+count*h*w:
        raise ValueError(f"不是有效的 MNIST 图像 IDX：{p}")
    return torch.from_numpy(np.frombuffer(payload, dtype=np.uint8, offset=16).copy().reshape(count,h,w))


class Pairs(Dataset):
    def __init__(self, images, ids, seed):
        self.images, self.ids = images, torch.as_tensor(ids)
        if len(ids) < 2:
            raise ValueError("每个数据划分至少需要两张图")
        self.seed = seed
        self.set_epoch(0)

    def set_epoch(self, epoch):
        # 循环错排保证同一对中索引不同；仅训练集每轮重新配对。
        g = torch.Generator().manual_seed(self.seed + epoch)
        order = torch.randperm(len(self.ids), generator=g)
        self.partner = torch.empty_like(order)
        self.partner[order] = order.roll(1)

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, k):
        a, b = self.ids[k], self.ids[self.partner[k]]
        return torch.stack((self.images[a], self.images[b])).float().div_(255)


class Encoder(nn.Module):
    def __init__(self, code_size):
        super().__init__()
        self.code_size = code_size
        self.net = nn.Sequential(nn.Conv2d(2,24,3,padding=1), nn.GELU(),
            nn.Conv2d(24,32,4,stride=2,padding=1), nn.GELU(),
            nn.Conv2d(32,48,4,stride=2,padding=1), nn.GELU(),
            nn.Conv2d(48,1,3,padding=1))

    def forward(self, x):
        y = self.net(x)
        y = F.adaptive_avg_pool2d(y, (self.code_size, self.code_size))
        return 2*math.pi*torch.sigmoid(y.float())


class OpticalDecoder(nn.Module):
    """Reference convention: J=[[c,-i*s*exp(+i*beta)],[-i*s*exp(-i*beta),c]].

    Component order is [L,R]. Labels follow the supplied code. Reflection and
    experimental handedness must be calibrated in the chosen propagation frame.
    beta is an effective coupling phase (director angle 2*theta), NOT voltage.
    """
    def __init__(self, c):
        super().__init__()
        self.h, self.s, self.p = c["target_size"], c["slm_size"], c["padding"]
        self.n = self.s+2*self.p
        self.offset = (self.n-self.h)//2
        self.beta = nn.Parameter(0.1*torch.randn(3,self.s,self.s))
        self.register_buffer("gamma", torch.tensor(c["retardance_rad"],dtype=torch.float32))
        self.register_buffer("aperture", F.pad(torch.ones(self.s,self.s), (self.p,)*4))
        f = torch.fft.fftfreq(self.n, d=c["pixel_pitch_m"], dtype=torch.float64)
        fy, fx = torch.meshgrid(f, f, indexing="ij")
        transverse = (c["wavelength_m"]*fx)**2 + (c["wavelength_m"]*fy)**2
        transfers = []
        for segment in c["segments"]:
            transfer = torch.ones(self.n,self.n,dtype=torch.complex128)
            for z, index in segment:
                q = index**2-transverse
                # 去掉无关的全局载波相位，避免 float32 大数相消。
                relative_kz = -2*math.pi/c["wavelength_m"]*transverse/(q.clamp_min(0).sqrt()+index)
                transfer *= torch.exp(1j*relative_kz*z)*(q>=0)
            transfers.append(transfer.to(torch.complex64))
        self.register_buffer("transfer", torch.stack(transfers))

    def propagate(self, u, k):
        # 不使用 fftshift；最后两维 FFT，不混排 batch 或偏振通道。
        return torch.fft.ifft2(torch.fft.fft2(u)*self.transfer[k])

    def modulate(self, u, k):
        beta = F.pad(self.beta[k], (self.p,)*4)
        c, s = torch.cos(self.gamma/2), torch.sin(self.gamma/2)
        l, r = u[:,0], u[:,1]
        phase = torch.exp(1j*beta)
        return torch.stack((c*l-1j*s*phase*r, -1j*s*phase.conj()*l+c*r), 1)*self.aperture

    def forward(self, code):
        # 相位型编码：24个宏像素各占4x4细采样，有限照明孔径96x96。
        fine = F.interpolate(code.float(),size=(self.h,self.h),mode="nearest")[:,0]
        field = F.pad(torch.exp(1j*fine)/self.h, (self.offset,)*4)
        u = torch.stack((field,torch.zeros_like(field)),1)  # 单位功率 LCP 入射
        u = self.propagate(u,0)
        for k in range(3):
            u = self.propagate(self.modulate(u,k),k+1)
        intensity = u.abs().square()
        roi = intensity[...,self.offset:self.offset+self.h,self.offset:self.offset+self.h]
        return roi, intensity.sum((-2,-1))  # 两偏振全窗口功率


class Model(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.encoder, self.optics = Encoder(c["code_size"]), OpticalDecoder(c)
        self.amp = c["amp_encoder"]

    def forward(self, x):
        with torch.autocast(device_type=x.device.type, dtype=torch.float16,
                            enabled=self.amp and x.is_cuda):
            code = self.encoder(x)
        # complex64 FFT：不在 autocast 内执行。
        roi, full_power = self.optics(code.float())
        return roi, code, full_power


def target_intensity(x, c):
    return x/x.sum((-2,-1),keepdim=True).clamp_min(1e-8)*(c["target_total_power"]/2)


def loss_fn(pred, target, c):
    scale = c["target_size"]**2/c["target_total_power"]
    p, t = pred*scale, target*scale
    mse = F.mse_loss(p,t)
    edge = F.l1_loss(p[...,1:,:]-p[...,:-1,:],t[...,1:,:]-t[...,:-1,:])
    edge += F.l1_loss(p[...,:,1:]-p[...,:,:-1],t[...,:,1:]-t[...,:,:-1])
    return mse+c["gradient_loss_weight"]*edge


def metrics(pred, target):
    # 每个目标峰值定义 data range；预测不独立归一化，不裁剪再计分。
    peak = target.amax((-2,-1),keepdim=True).clamp_min(1e-8)
    p,t = pred/peak,target/peak
    mse = (p-t).square().mean((-2,-1))
    psnr = -10*torch.log10(mse.clamp_min(1e-12))
    v = torch.arange(11,device=p.device,dtype=p.dtype)-5
    g = torch.exp(-v.square()/4.5); g = g/g.sum()
    kernel = (g[:,None]*g[None,:]).expand(2,1,11,11).contiguous()
    def blur(x): return F.conv2d(x,kernel,groups=2)
    a,b = blur(p),blur(t)
    va,vb,cov = blur(p*p)-a*a,blur(t*t)-b*b,blur(p*t)-a*b
    ssim = ((2*a*b+.01**2)*(2*cov+.03**2)/
            ((a*a+b*b+.01**2)*(va.clamp_min(0)+vb.clamp_min(0)+.03**2))).mean((-2,-1))
    return psnr,ssim


def write_csv(path, rows):
    if not rows: return
    with open(path,"w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def save_examples(out, x, pred, target, code, start, count):
    for i in range(min(len(x),count)):
        folder=out/f"sample_{start+i:04d}";folder.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(folder/"arrays.npz",input_images=x[i].cpu().numpy(),
            code_phase_rad=code[i,0].cpu().numpy(), prediction=pred[i].cpu().numpy(),
            target=target[i].cpu().numpy())
        tiles=[]
        for channel,name in enumerate(("LCP","RCP")):
            peak=float(target[i,channel].max().clamp_min(1e-8))
            for data,label in ((x[i,channel],"input"),(pred[i,channel]/peak,"reconstruction")):
                im=Image.fromarray((data.cpu().numpy()*255).clip(0,255).round().astype("uint8"))
                im.save(folder/f"{name}_{label}.png");tiles.append((im,f"{name} {label}"))
        im=Image.fromarray((code[i,0].cpu().numpy()/(2*math.pi)*255).round().astype("uint8"))
        im.save(folder/"code24.png");tiles.insert(2,(im,"Phase code / 2pi"))
        panel=Image.new("RGB",(5*210,240),"white");draw=ImageDraw.Draw(panel)
        for j,(tile,label) in enumerate(tiles):
            panel.paste(tile.resize((192,192),Image.Resampling.NEAREST),(j*210+9,35))
            draw.text((j*210+9,10),label,fill="black")
        panel.save(folder/"comparison.png")


@torch.no_grad()
def evaluate(model,loader,device,c,out=None):
    model.eval();total=0.;count=0;rows=[];saved=0
    for raw in loader:
        x=F.interpolate(raw.to(device,non_blocking=True),size=(c["target_size"],)*2,mode="bilinear",align_corners=False)
        pred,code,full=model(x);target=target_intensity(x,c)
        total+=float(loss_fn(pred,target,c))*len(x);count+=len(x)
        if out is not None:
            psnr,ssim=metrics(pred,target)
            roi=pred.sum((-2,-1))
            for i in range(len(x)):
                rows.append({"pair":len(rows),"psnr_L_dB":float(psnr[i,0]),"psnr_R_dB":float(psnr[i,1]),
                    "ssim_L":float(ssim[i,0]),"ssim_R":float(ssim[i,1]),
                    "roi_efficiency_L":float(roi[i,0]),"roi_efficiency_R":float(roi[i,1]),
                    "full_power_L":float(full[i,0]),"full_power_R":float(full[i,1])})
            n=min(len(x),max(0,c["save_examples"]-saved))
            save_examples(out,x,pred,target,code,saved,n);saved+=n
    if out is not None:
        write_csv(out/"test_metrics.csv",rows)
        means={k:sum(r[k] for r in rows)/len(rows) for k in rows[0] if k!="pair"}
        (out/"test_summary.json").write_text(json.dumps(means,indent=2),encoding="utf-8")
        print("独立测试集结果：",means)
    return total/count


def self_test(c, device):
    """Use production optical dimensions; no dataset download or training claim."""
    model=Model(c).to(device)
    x=torch.rand(2,2,c["target_size"],c["target_size"],device=device)
    pred,code,power=model(x)
    assert code.shape==(2,1,c["code_size"],c["code_size"])
    assert pred.shape==x.shape and bool((power.sum(1)<=1.0001).all())
    loss=loss_fn(pred,target_intensity(x,c),c);loss.backward()
    for name,p in model.named_parameters():
        assert p.grad is not None and bool(torch.isfinite(p.grad).all()),name
        assert float(p.grad.abs().sum())>0,name
    optics=model.optics
    u=torch.randn(2,2,optics.n,optics.n,dtype=torch.complex64,device=device)*optics.aperture
    ju=optics.modulate(u,0)
    assert torch.allclose(u.abs().square().sum(),ju.abs().square().sum(),rtol=1e-5)
    # Pure L input must match the sign convention of the supplied reference.
    u[:,1]=0
    j=optics.modulate(u,0)
    expected=-1j*torch.sin(optics.gamma/2)*torch.exp(-1j*F.pad(optics.beta[0],(optics.p,)*4))*u[:,0]
    assert torch.allclose(j[:,1],expected,atol=1e-6)
    before=optics.propagate(u,0)
    assert torch.allclose(u.abs().square().sum(),before.abs().square().sum(),rtol=1e-5)
    opt=torch.optim.Adam(model.parameters(),lr=c["learning_rate"]);opt.step()
    print("PASS: shapes, gradients, optimizer, Jones power/sign, propagation power; device=",device)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test",action="store_true")
    parser.add_argument("--cpu",action="store_true",help="仅调试时显式使用 CPU")
    parser.add_argument("--config",help="可选 JSON 文件覆盖文件开头配置")
    args=parser.parse_args();c=dict(CONFIG)
    if args.config:
        overrides=json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
        unknown=set(overrides)-set(c)
        if unknown: raise ValueError(f"未知配置：{unknown}")
        c.update(overrides)
    if args.cpu: c["device"]="cpu"
    validate(c)
    random.seed(c["seed"]);np.random.seed(c["seed"]);torch.manual_seed(c["seed"])
    if c["device"]=="cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA 不可用。安装 CUDA 版 PyTorch 并检查 NVIDIA 驱动。不会自动退回 CPU。")
        device=torch.device(f"cuda:{c['cuda_index']}");torch.cuda.set_device(device)
        torch.cuda.manual_seed_all(c["seed"])
        torch.backends.cudnn.benchmark=True
        print("GPU:",torch.cuda.get_device_name(device),"PyTorch:",torch.__version__,"CUDA:",torch.version.cuda)
    elif c["device"]=="cpu": device=torch.device("cpu")
    else: raise ValueError("device 必须为 cuda 或 cpu")
    if args.self_test: self_test(c,device);return
    if c["mode"]=="test" and not c["checkpoint"]:
        raise ValueError("test 模式必须设置 checkpoint")
    model=Model(c).to(device)
    optimizer=torch.optim.Adam(model.parameters(),lr=c["learning_rate"])
    scaler=torch.amp.GradScaler("cuda",enabled=c["amp_encoder"] and device.type=="cuda")
    start=0;best=float("inf");history=[];best_model=None
    if c["checkpoint"]:
        ck=torch.load(c["checkpoint"],map_location=device,weights_only=True)
        for key in ("target_size","code_size","slm_size","padding","pixel_pitch_m","wavelength_m",
                    "retardance_rad","segments","target_total_power"):
            if json.dumps(c[key])!=json.dumps(ck["config"][key]):
                raise ValueError(f"checkpoint 配置不匹配：{key}")
        model.load_state_dict(ck["model"])
        if c["mode"]=="train":
            optimizer.load_state_dict(ck["optimizer"]);scaler.load_state_dict(ck["scaler"])
            start=ck["epoch"];best=ck["best_val"];history=ck["history"]
            best_model=ck["best_model"]
    out=Path(c["output_dir"])/datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out.mkdir(parents=True,exist_ok=False)
    (out/"config.json").write_text(json.dumps(c,indent=2,ensure_ascii=False),encoding="utf-8")
    (out/"environment.json").write_text(json.dumps({"torch":str(torch.__version__),"cuda":torch.version.cuda,
        "device":str(device),"gpu":torch.cuda.get_device_name(device) if device.type=="cuda" else None},indent=2),encoding="utf-8")
    def loader(ds,train=False):
        return DataLoader(ds,batch_size=c["batch_size"],shuffle=train,num_workers=c["num_workers"],
            pin_memory=device.type=="cuda",persistent_workers=False,
            generator=torch.Generator().manual_seed(c["seed"]))
    if c["mode"]=="train":
        images=read_mnist(c["mnist_dir"],True,c["download_mnist"])
        order=np.random.default_rng(c["seed"]).permutation(len(images))
        if c["val_size"]>len(images)-2: raise ValueError("val_size 太大")
        val_ids=order[:c["val_size"]];train_ids=order[c["val_size"]:]
        if c["train_limit"]>0: train_ids=train_ids[:c["train_limit"]]
        np.savez(out/"split_indices.npz",train=train_ids,val=val_ids)
        train_ds=Pairs(images,train_ids,c["seed"]);val_ds=Pairs(images,val_ids,c["seed"]+100000)
        train_loader,val_loader=loader(train_ds,True),loader(val_ds)
        for epoch in range(start,c["epochs"]):
            begin=time.perf_counter();train_ds.set_epoch(epoch);model.train();total=0.;count=0
            for batch,raw in enumerate(train_loader):
                x=F.interpolate(raw.to(device,non_blocking=True),size=(c["target_size"],)*2,mode="bilinear",align_corners=False)
                optimizer.zero_grad(set_to_none=True)
                pred,_,_=model(x);loss=loss_fn(pred,target_intensity(x,c),c)
                if not bool(torch.isfinite(loss)): raise FloatingPointError("loss 非有限数；检查学习率与光学参数")
                scaler.scale(loss).backward();scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_(model.parameters(),c["grad_clip"])
                scaler.step(optimizer);scaler.update()
                total+=float(loss.detach())*len(x);count+=len(x)
                if batch%100==0: print(f"Epoch {epoch+1}/{c['epochs']} batch {batch+1}/{len(train_loader)} loss={float(loss):.6f}",flush=True)
            val=evaluate(model,val_loader,device,c)
            improved=val<best;best=min(best,val)
            if improved:
                best_model={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            row={"epoch":epoch+1,"train_loss":total/count,"val_loss":val,"seconds":time.perf_counter()-begin}
            history.append(row);print(row,flush=True);write_csv(out/"history.csv",history)
            ck={"model":model.state_dict(),"optimizer":optimizer.state_dict(),"scaler":scaler.state_dict(),
                "config":c,"epoch":epoch+1,"best_val":best,"history":history,"best_model":best_model}
            torch.save(ck,out/"last.pt")
            if improved: torch.save(ck,out/"best.pt")
        # 新训练或续训没有超越旧最佳时，不把最后一轮冒充最佳。
        if (out/"best.pt").exists():
            model.load_state_dict(torch.load(out/"best.pt",map_location=device,weights_only=True)["model"])
            tested_checkpoint=str(out/"best.pt")
        elif best_model is not None:
            model.load_state_dict(best_model)
            tested_checkpoint=c["checkpoint"]+" [embedded best_model]"
        else: raise RuntimeError("没有可测试的训练权重")
    else: tested_checkpoint=c["checkpoint"]
    (out/"tested_checkpoint.txt").write_text(tested_checkpoint,encoding="utf-8")
    images=read_mnist(c["mnist_dir"],False,c["download_mnist"])
    ids=np.arange(len(images))
    if c["test_limit"]>0: ids=ids[:c["test_limit"]]
    evaluate(model,loader(Pairs(images,ids,c["seed"]+200000)),device,c,out)
    beta=torch.remainder(model.optics.beta.detach(),2*math.pi).cpu().numpy()
    np.save(out/"layer_beta_rad.npy",beta)
    for k,phase in enumerate(beta,1):
        np.savetxt(out/f"layer_{k}_beta_rad.txt",phase,fmt="%.8f")
        Image.fromarray((phase/(2*math.pi)*255).round().astype("uint8")).save(out/f"layer_{k}_phase_preview.png")
    print("完成，结果保存在：",out)


if __name__=="__main__":
    multiprocessing.freeze_support()
    main()
