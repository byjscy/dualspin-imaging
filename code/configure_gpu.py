"""Persist OptiX GPU-only Cycles preferences and update this project's scene."""
import bpy, os, json

OUT=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'models')
p=bpy.context.preferences.addons['cycles'].preferences
p.compute_device_type='OPTIX'
p.get_devices()
gpu=[d for d in p.devices if d.type=='OPTIX']
if not gpu:raise RuntimeError('No OptiX device found; preferences not saved.')
for d in p.devices:d.use=d.type=='OPTIX'
bpy.ops.wm.save_userpref()
path=os.path.join(OUT,'optical_system_v002.blend')
bpy.ops.wm.open_mainfile(filepath=path)
for scene in bpy.data.scenes:
    scene.render.engine='CYCLES'
    scene.cycles.device='GPU'
    scene.cycles.use_denoising=True
    scene.cycles.use_preview_denoising=True
    if hasattr(scene.cycles,'denoiser'):scene.cycles.denoiser='OPTIX'
    if hasattr(scene.cycles,'preview_denoiser'):scene.cycles.preview_denoiser='OPTIX'
    if hasattr(scene.cycles,'denoising_use_gpu'):scene.cycles.denoising_use_gpu=True
    if hasattr(scene.cycles,'preview_denoising_use_gpu'):scene.cycles.preview_denoising_use_gpu=True
    scene.cycles.preview_samples=24
    scene.cycles.use_adaptive_sampling=True
bpy.ops.wm.save_as_mainfile(filepath=path)
report={'backend':p.compute_device_type,'devices':[{'name':d.name,'type':d.type,'enabled':bool(d.use)} for d in p.devices], 'scenes':[{'name':s.name,'render_device':s.cycles.device,'denoiser':s.cycles.denoiser,'preview_denoiser':s.cycles.preview_denoiser} for s in bpy.data.scenes]}
with open(os.path.join(OUT,'gpu_settings.json'),'w',encoding='utf-8') as f:json.dump(report,f,indent=2)
print('GPU_CONFIGURED',json.dumps(report),flush=True)
