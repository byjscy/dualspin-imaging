"""Dual-image phase encoding and three-stage effective-Jones reconstruction.

This is a proposed differentiable research model, NOT a calibrated 2K73 model.
Input: two intensity images [B,2,96,96]. Electronic output: ONE 24x24 phase map.
Input polarization: LCP. Output: simultaneous LCP/RCP intensity channels.
Circular basis matches the supplied PDF: |L>=(1,i)/sqrt(2), |R>=(1,-i)/sqrt(2).
No claim of diffraction-limited resolution follows from the output array size.
"""
import argparse, json, math, os, random
from pathlib import Path

def scalar_physics_check():
    """Dependency-free check of the exact Jones formula used below."""
    import cmath
    worst=0.0
    for gamma in [0, math.pi/5, math.pi/2, math.pi]:
        for theta in [0,.17,1.2,2.8]:
            c,s=math.cos(gamma/2),math.sin(gamma/2)
            j=((c,-1j*s*cmath.exp(-2j*theta)),(-1j*s*cmath.exp(2j*theta),c))
            for i in range(2):
                for k in range(2):
                    value=sum(j[a][i].conjugate()*j[a][k] for a in range(2))
                    worst=max(worst,abs(value-(1 if i==k else 0)))
    assert worst<1e-12,worst
    print(json.dumps({'Jones_unitarity_max_error':worst,'basis':'L=(1,i), R=(1,-i)','half_wave_conversion_power':math.sin(math.pi/2)**2}))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--physics-check',action='store_true')
    ap.add_argument('--self-test',action='store_true',help='Check tensor shapes, propagation, power and gradient flow; requires torch')
    ap.add_argument('--dataset',choices=['mnist','synthetic'],default='mnist')
    ap.add_argument('--data',default='data');ap.add_argument('--download',action='store_true')
    ap.add_argument('--output',default='runs/dual_sr');ap.add_argument('--checkpoint')
    ap.add_argument('--eval-only',action='store_true');ap.add_argument('--epochs',type=int,default=30)
    ap.add_argument('--limit',type=int,default=4096);ap.add_argument('--batch-size',type=int,default=8)
    ap.add_argument('--lr',type=float,default=1e-3);ap.add_argument('--seed',type=int,default=7)
    ap.add_argument('--gamma',type=float,default=math.pi/5)
    ap.add_argument('--pixel-pitch',type=float,default=8e-6,help='Fine simulation sampling pitch, metres; macro pixel pitch is 4x this')
    ap.add_argument('--wavelength',type=float,default=532e-9)
    ap.add_argument('--distances',type=float,nargs=4,default=[.05,.002,.002,.05],metavar=('Z0','Z1','Z2','Z3'))
    args=ap.parse_args()
    if args.physics_check:scalar_physics_check();return
    try:
        import torch
        from torch import nn
        import torch.nn.functional as F
        from torch.utils.data import Dataset,DataLoader
        import numpy as np
        from PIL import Image,ImageDraw,ImageFont
    except ImportError as e:
        raise SystemExit('Missing dependency: '+str(e)+'. Install torch, numpy and pillow; MNIST also requires torchvision. See dual_sr_README.md.')
    torch.manual_seed(args.seed);random.seed(args.seed);np.random.seed(args.seed)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    H,N,PAD=96,24,48

    class PairDataset(Dataset):
        def __init__(self,train):
            self.train=train
            if args.dataset=='mnist':
                from torchvision.datasets import MNIST
                self.ds=MNIST(args.data,train=train,download=args.download)
            else:self.ds=None
            self.length=min(args.limit,len(self.ds)) if self.ds is not None else args.limit
            if self.length<2:raise ValueError('At least two images are required.')
            rng=np.random.default_rng(args.seed+(0 if train else 12345))
            self.order=rng.permutation(self.length)
        def __len__(self):return self.length
        def image(self,index):
            if self.ds is not None:im=self.ds[index][0].resize((H,H),Image.Resampling.BILINEAR)
            else:
                # Debug-only data; never use this as evidence for MNIST performance.
                rng=random.Random(index+(0 if self.train else 100000))
                im=Image.new('L',(H,H),0);d=ImageDraw.Draw(im)
                fontpath='C:/Windows/Fonts/arial.ttf' if os.name=='nt' else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
                font=ImageFont.truetype(fontpath,rng.randrange(55,80))
                d.text((rng.randrange(8,25),rng.randrange(0,14)),str(rng.randrange(10)),font=font,fill=255)
            return torch.from_numpy(np.asarray(im,dtype=np.float32).copy()/255)
        def __getitem__(self,k):
            j=int(self.order[(k+1)%self.length])
            if j==k:j=(j+1)%self.length
            return torch.stack([self.image(k),self.image(j)])

    class Encoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.net=nn.Sequential(nn.Conv2d(2,24,3,padding=1),nn.GELU(),nn.Conv2d(24,32,4,stride=2,padding=1),nn.GELU(),nn.Conv2d(32,32,4,stride=2,padding=1),nn.GELU(),nn.Conv2d(32,1,3,padding=1))
        def forward(self,x):return 2*math.pi*torch.sigmoid(self.net(x))

    class EffectiveJones(nn.Module):
        def __init__(self):
            super().__init__()
            # beta=2*theta; trainable phase, not a guessed voltage calibration.
            self.beta=nn.Parameter(.1*torch.randn(3,H,H))
            self.register_buffer('gamma',torch.tensor(args.gamma,dtype=torch.float32))
            freq=torch.fft.fftfreq(H+2*PAD,d=args.pixel_pitch,dtype=torch.float64)
            fy,fx=torch.meshgrid(freq,freq,indexing='ij')
            transverse=(args.wavelength*fx)**2+(args.wavelength*fy)**2
            q=1-transverse
            # Exact scalar angular spectrum, unshifted FFT convention.
            # All frequencies propagate for the default optical sampling pitch.
            # Drop the spatially uniform carrier phase and evaluate sqrt(q)-1
            # without cancellation. Build in float64, use complex64 FFTs.
            relative_kz=-(2*math.pi/args.wavelength)*transverse/(torch.sqrt(q.clamp_min(0))+1)
            transfer=torch.stack([torch.exp(1j*relative_kz*z)*(q>=0) for z in args.distances]).to(torch.complex64)
            self.register_buffer('transfer',transfer)
            self.register_buffer('aperture',F.pad(torch.ones(H,H),(PAD,)*4))
        def propagate(self,u,k):return torch.fft.ifft2(torch.fft.fft2(u)*self.transfer[k])
        def layer(self,u,k):
            phase=F.pad(self.beta[k],(PAD,)*4)
            c,s=torch.cos(self.gamma/2),torch.sin(self.gamma/2)
            l,r=u[:,0],u[:,1]
            left=c*l-1j*s*torch.exp(-1j*phase)*r
            right=-1j*s*torch.exp(1j*phase)*l+c*r
            return torch.stack((left,right),dim=1)*self.aperture
        def forward(self,phase):
            # A 24x24 modulator has 4x4 constant fine samples per macro pixel.
            fine=F.interpolate(phase,size=(H,H),mode='nearest')[:,0]
            l=F.pad(torch.exp(1j*fine)/H,(PAD,)*4)
            u=torch.stack((l,torch.zeros_like(l)),dim=1)
            power={'input':u.abs().square().sum((-3,-2,-1))}
            u=self.propagate(u,0)
            for k in range(3):
                u=self.layer(u,k);power['after_layer_'+str(k+1)]=u.abs().square().sum((-3,-2,-1))
                u=self.propagate(u,k+1)
            intensity=u.abs().square()
            power['full_output']=intensity.sum((-3,-2,-1))
            crop=intensity[...,PAD:PAD+H,PAD:PAD+H]
            power['detected']=crop.sum((-3,-2,-1))
            return crop,power

    class Model(nn.Module):
        def __init__(self):super().__init__();self.encoder=Encoder();self.decoder=EffectiveJones()
        def forward(self,x):
            phase=self.encoder(x);out,power=self.decoder(phase);return out,phase,power
    model=Model().to(device)
    def targets(x):
        # Each channel is assigned half of unit incident power.
        return .5*x/x.sum((-2,-1),keepdim=True).clamp_min(1e-8)
    def loss_fn(pred,target):
        # Rescale intensity units, not per-output contrast, to keep gradients useful.
        return F.mse_loss(pred*H*H,target*H*H)
    def ssim_per_channel(pred,target):
        t=torch.arange(11,device=pred.device,dtype=pred.dtype)-5
        g=torch.exp(-t.square()/(2*1.5**2));g=g/g.sum()
        kernel=(g[:,None]*g[None,:]).expand(2,1,11,11).contiguous()
        def blur(x):return F.conv2d(x,kernel,groups=2)
        a,b=blur(pred),blur(target)
        va=blur(pred.square())-a.square();vb=blur(target.square())-b.square()
        cov=blur(pred*target)-a*b
        score=((2*a*b+.01**2)*(2*cov+.03**2))/((a.square()+b.square()+.01**2)*(va+vb+.03**2))
        return score.mean((-2,-1))
    if args.self_test:
        x=torch.rand(2,2,H,H,device=device)
        out,phase,power=model(x)
        assert tuple(phase.shape)==(2,1,N,N) and tuple(out.shape)==(2,2,H,H)
        for p in power.values():assert bool(torch.isfinite(p).all()) and float(p.max())<=1.0001
        loss=loss_fn(out,targets(x));loss.backward()
        assert all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters())
        assert float(model.encoder.net[0].weight.grad.abs().sum())>0
        # In a lossless plane, the circular-basis Jones transformation is unitary.
        z=torch.randn(2,2,H+2*PAD,H+2*PAD,device=device,dtype=torch.complex64)*model.decoder.aperture
        j=model.decoder.layer(z,0)
        assert torch.allclose(z.abs().square().sum(),j.abs().square().sum(),rtol=1e-5)
        print('TENSOR_AND_GRADIENT_TEST_OK',device,float(loss));return
    outdir=Path(args.output);outdir.mkdir(parents=True,exist_ok=True)
    if args.checkpoint:
        # Only load local checkpoints created by this program; no pickled objects required.
        saved=torch.load(args.checkpoint,map_location=device,weights_only=True)
        optical_keys=['gamma','pixel_pitch','wavelength','distances']
        for key in optical_keys:
            if saved['config'][key]!=vars(args)[key]:raise ValueError('Checkpoint optical setting mismatch: '+key)
        model.load_state_dict(saved['state_dict'])
    if args.eval_only and not args.checkpoint:raise ValueError('--eval-only requires --checkpoint')
    trainloader=DataLoader(PairDataset(True),batch_size=args.batch_size,shuffle=True,num_workers=0)
    testloader=DataLoader(PairDataset(False),batch_size=args.batch_size,shuffle=False,num_workers=0)
    optimizer=torch.optim.Adam(model.parameters(),lr=args.lr)
    history=[]
    if not args.eval_only:
        for epoch in range(args.epochs):
            model.train();total=0.;count=0
            for x in trainloader:
                x=x.to(device);pred,phase,power=model(x);loss=loss_fn(pred,targets(x))
                optimizer.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step()
                total+=float(loss.detach())*x.shape[0];count+=x.shape[0]
            model.eval();vtotal=0.;vcount=0
            with torch.no_grad():
                for x in testloader:
                    x=x.to(device);pred,_,_=model(x);vtotal+=float(loss_fn(pred,targets(x)))*x.shape[0];vcount+=x.shape[0]
            row={'epoch':epoch+1,'train_loss':total/count,'test_loss':vtotal/vcount};history.append(row);print(json.dumps(row),flush=True)
            torch.save({'state_dict':model.state_dict(),'config':vars(args)},outdir/'last.pt')
    model.eval();metrics=[]
    with torch.no_grad():
        for batch,x in enumerate(testloader):
            x=x.to(device);pred,phase,power=model(x);target=targets(x)
            # PSNR uses a common target-based range per image pair, never output-wise normalization.
            scale=target.amax((-3,-2,-1),keepdim=True).clamp_min(1e-8)
            mse=((pred-target)/scale).square().mean((-2,-1)).clamp_min(1e-12)
            psnr=-10*torch.log10(mse)
            ssim=ssim_per_channel(pred/scale,target/scale)
            for i in range(len(x)):
                metrics.append({'psnr_L_dB':float(psnr[i,0]),'psnr_R_dB':float(psnr[i,1]),'ssim_L':float(ssim[i,0]),'ssim_R':float(ssim[i,1]),'detection_efficiency':float(power['detected'][i]),'full_output_power':float(power['full_output'][i])})
            if batch==0:
                np.save(outdir/'code_phase24.npy',phase[0,0].cpu().numpy())
                np.save(outdir/'predicted_intensity96.npy',pred[0].cpu().numpy())
                np.save(outdir/'target_intensity96.npy',target[0].cpu().numpy())
                np.save(outdir/'beta_three_layers.npy',model.decoder.beta.cpu().numpy())
                code=(phase[0,0].cpu().numpy()/(2*math.pi)*255).round().astype(np.uint8)
                Image.fromarray(code).save(outdir/'code24.png')
                display_scale=float(target[0].max())
                for c,label in enumerate(['L','R']):
                    Image.fromarray((pred[0,c].cpu().numpy()/display_scale*255).clip(0,255).astype(np.uint8)).save(outdir/('reconstruction_'+label+'.png'))
    report={'model':'effective lossless Jones cells + finite apertures + free-space propagation','hardware_calibrated':False,'dataset':args.dataset,'device':str(device),'config':vars(args),'history':history,'metrics':metrics,'mean_psnr_L_dB':sum(m['psnr_L_dB'] for m in metrics)/len(metrics),'mean_psnr_R_dB':sum(m['psnr_R_dB'] for m in metrics)/len(metrics),'mean_detection_efficiency':sum(m['detection_efficiency'] for m in metrics)/len(metrics),'limitations':['Output sampling is not proof of diffraction-limit super-resolution.','Polarization crosstalk requires independent calibration targets.','No commercial LCOS voltage/phase or reflection handedness calibration is included.','Synthetic data is for debugging only.']}
    (outdir/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('SAVED',outdir.resolve())

if __name__=='__main__':main()
