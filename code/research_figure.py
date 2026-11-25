"""Build a four-panel scientific principle figure in Blender.
All optical hardware remains in an independent editable source scene.
Text positions are exported for native PowerPoint COM labels.
"""
import bpy, os, math, json
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,'models','figure');os.makedirs(OUT,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT,'models','optical_system_v004.blend'))
source=bpy.context.scene;source.name='01_Reflective_apparatus'
for o in source.objects:
    if o.name in ['Studio ground','Optical breadboard','Breadboard mounting grid 50 mm (visual)'] or o.name in bpy.data.collections['08_Annotations'].objects:
        o.hide_render=True
    if any(w in o.name for w in ['workstation monitor','Input image','Encoded electronic pattern','Monitor caption','Workstation monitor','Dual output readout','Readout image','Readout labels','stage note','Scene title','Scene subtitle','Concept notice','Beam legend']):o.hide_render=True
cam=bpy.data.objects['Camera overview'];source.camera=cam
cam.data.ortho_scale=3.65
source.render.resolution_x=3000;source.render.resolution_y=1200;source.render.resolution_percentage=100
source.render.film_transparent=True;source.render.image_settings.media_type='IMAGE';source.render.image_settings.file_format='PNG';source.render.image_settings.color_mode='RGBA'
source.render.engine='CYCLES';source.cycles.device='GPU';source.cycles.samples=96
source.render.filepath=os.path.join(OUT,'apparatus.png')
bpy.ops.render.render(write_still=True)
bpy.context.view_layer.update()
projected={}
for key,tag in [('02_Encoder','Encoding SLM'),('03_SLM_A','LCOS 1'),('04_SLM_B','LCOS 2'),('05_SLM_C','LCOS 3')]:
    o=next(o for o in bpy.data.collections[key].objects if 'active aperture' in o.name)
    co=world_to_camera_view(source,cam,o.location);projected[tag]=[co.x,co.y]

scene=bpy.data.scenes.new('02_Research_figure');bpy.context.window.scene=scene
W,H=24,15
font=bpy.data.fonts.load('C:/Windows/Fonts/arial.ttf');boldfont=bpy.data.fonts.load('C:/Windows/Fonts/arialbd.ttf')
def rgba(hex):
    h=hex.lstrip('#');rgb=[int(h[i:i+2],16)/255 for i in [0,2,4]]
    return tuple((v/12.92 if v<.04045 else ((v+.055)/1.055)**2.4) for v in rgb)+(1,)
def mat(name,hex):
    m=bpy.data.materials.new(name);m.use_nodes=True;nt=m.node_tree;nt.nodes.clear()
    out=nt.nodes.new('ShaderNodeOutputMaterial');e=nt.nodes.new('ShaderNodeEmission');e.inputs['Color'].default_value=rgba(hex);nt.links.new(e.outputs[0],out.inputs[0]);return m
ink=mat('Figure ink','#203743');muted=mat('Figure secondary','#60747F');rule=mat('Figure separators','#DCE4E8')
blue=mat('LCP channel','#1886AC');orange=mat('RCP channel','#D2763D');purple=mat('Liquid crystal','#8874AD')
green=mat('Shared optical field','#4B9E7A');pale=mat('Encoder fill','#EAF3F1');violet=mat('LC fill','#F0ECF6');grayfill=mat('Light fill','#F4F7F8')
WHITE=mat('White','#FFFFFF')
TEXTS=[]
def mesh(name,verts,faces,m):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(name,me);scene.collection.objects.link(o);me.materials.append(m);return o
def rect(name,x,y,w,h,m,z=0):return mesh(name,[(x,y,z),(x+w,y,z),(x+w,y+h,z),(x,y+h,z)],[(0,1,2,3)],m)
def line(name,pts,m=muted,r=.012,z=.04):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.bevel_depth=r;cu.bevel_resolution=2;s=cu.splines.new('POLY');s.points.add(len(pts)-1)
    for p,xy in zip(s.points,pts):p.co=(xy[0],xy[1],z,1)
    o=bpy.data.objects.new(name,cu);scene.collection.objects.link(o);cu.materials.append(m);return o
def arrow(name,a,b,m=muted,r=.017):
    line(name,[a,b],m,r)
    d=(Vector(b)-Vector(a)).normalized();n=Vector((-d.y,d.x));end=Vector(b);base=end-d*.15
    mesh(name+' arrowhead',[(end.x,end.y,.07),(*(base+n*.07),.07),(*(base-n*.07),.07)],[(0,1,2)],m)
def text(body,x,y,size=.22,m=ink,bold=False,align='LEFT',width=None):
    cu=bpy.data.curves.new(body[:40],'FONT');cu.body=body;cu.size=size;cu.font=boldfont if bold else font;cu.align_x=align
    o=bpy.data.objects.new(body[:40],cu);scene.collection.objects.link(o);o.location=(x,y,.15);cu.materials.append(m)
    bpy.context.view_layer.update();w=o.dimensions.x
    TEXTS.append({'text':body,'x':x,'baseline':y,'size':size,'bold':bold,'align':align,'color':m.name,'width':max(w+.12,width or 0),'height':max(o.dimensions.y+.1,size*1.7)})
    return o
def image(name,path,x,y,w,h,border=None):
    im=bpy.data.images.load(path,check_existing=True);im.pack()
    m=bpy.data.materials.new(name+' texture');m.use_nodes=True;nt=m.node_tree;nt.nodes.clear();out=nt.nodes.new('ShaderNodeOutputMaterial');tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im;tex.interpolation='Closest' if 'input_' in path or 'code_' in path else 'Linear'
    em=nt.nodes.new('ShaderNodeEmission');nt.links.new(tex.outputs['Color'],em.inputs['Color'])
    mix=nt.nodes.new('ShaderNodeMixShader');tr=nt.nodes.new('ShaderNodeBsdfTransparent');nt.links.new(tex.outputs['Alpha'],mix.inputs[0]);nt.links.new(tr.outputs[0],mix.inputs[1]);nt.links.new(em.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],out.inputs[0])
    o=rect(name,x,y,w,h,m,.025);uv=o.data.uv_layers.new(name='UVMap')
    for p,c in zip(uv.data,[(0,0),(1,0),(1,1),(0,1)]):p.uv=c
    if border:line(name+' border',[(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)],border,.014)
    return o

text('Dual-channel polarization super-resolution imaging',.65,14.10,.47,bold=True)
text('Joint electronic encoding and three-stage polarization-sensitive optical decoding',.67,13.58,.245,m=muted)
line('Title separator',[(.65,13.15),(23.35,13.15)],rule,.012)
text('a',.65,12.58,.32,bold=True);text('Information flow and reconstruction target',1.15,12.58,.29,bold=True)
f3=os.path.join(ROOT,'models','input_3_96.png');f7=os.path.join(ROOT,'models','input_7_96.png');fc=os.path.join(ROOT,'models','code_24_demo.png')
image('Target A',f3,.90,10.70,1.05,1.05,blue);image('Target B',f7,2.15,10.70,1.05,1.05,orange)
text('I_A',1.42,10.34,.23,blue,True,'CENTER');text('I_B',2.67,10.34,.23,orange,True,'CENTER')
text('Two 96 × 96 targets',2.05,9.90,.21,muted,align='CENTER')
arrow('Inputs to encoder',(3.45,11.22),(4.35,11.22))
rect('Electronic encoder',4.55,10.43,2.12,1.55,pale)
line('Encoder outline',[(4.55,10.43),(6.67,10.43),(6.67,11.98),(4.55,11.98),(4.55,10.43)],green,.014)
text('Electronic',5.61,11.42,.26,bold=True,align='CENTER');text('encoder Eψ',5.61,10.98,.26,bold=True,align='CENTER')
text('Learned joint encoding',5.61,9.90,.21,muted,align='CENTER')
arrow('Encoder to code',(6.88,11.22),(7.60,11.22))
image('24x24 code',fc,7.90,10.60,1.25,1.25,green)
text('C = Eψ(I_A, I_B)',8.53,10.20,.23,align='CENTER');text('One 24 × 24 phase code',8.53,9.90,.21,muted,align='CENTER')
arrow('Code to decoder',(9.38,11.22),(10.05,11.22),green)
for k in range(3):
    x=10.30+k*.64
    mesh('Layer icon '+str(k),[(x,10.50,.03),(x+.46,10.67,.03),(x+.46,11.95,.03),(x,11.78,.03)],[(0,1,2,3)],violet)
    line('Layer rim '+str(k),[(x,10.50),(x+.46,10.67),(x+.46,11.95),(x,11.78),(x,10.50)],purple,.014)
text('J1     J2     J3',11.15,10.13,.23,purple,True,'CENTER');text('Polarization-sensitive decoder',11.55,9.90,.21,muted,align='CENTER')
arrow('Decoder to analyzer',(12.28,11.22),(13.25,11.22),green)
rect('Analyzer',13.48,10.54,2.10,1.38,grayfill)
text('QWP + PBS',14.53,11.31,.26,bold=True,align='CENTER');text('L / R analysis',14.53,10.85,.21,muted,align='CENTER')
line('LCP route',[(15.58,11.22),(16.05,11.22),(16.05,11.75)],blue,.022);arrow('LCP output',(16.05,11.75),(17.03,11.75),blue,.022)
line('RCP route',[(15.58,11.22),(16.05,11.22),(16.05,10.40)],orange,.022);arrow('RCP output',(16.05,10.40),(17.03,10.40),orange,.022)
image('Illustrative L output',f3,17.32,11.25,.95,.95,blue);image('Illustrative R output',f7,17.32,9.90,.95,.95,orange)
text('LCP: Î_A  (96 × 96)',18.60,11.73,.265,blue,True);text('RCP: Î_B  (96 × 96)',18.60,10.38,.265,orange,True)
text('Illustrative target appearance',18.60,9.89,.20,muted)
line('Panel a bottom',[(.65,9.50),(23.35,9.50)],rule,.012)

text('b',.65,8.99,.32,bold=True);text('Folded reflective implementation',1.15,8.99,.29,bold=True)
image('Editable hardware render',os.path.join(OUT,'apparatus.png'),.65,4.20,14.00,4.65)
for name,(u,v) in projected.items():
    x=.65+14*u;y=4.20+4.65*v
    ty=y+.45
    text(name,x,ty,.19,m=ink,bold=True,align='CENTER');line('Leader '+name,[(x,ty-.05),(x,y+.08)],muted,.008)
text('532 nm laser → reflective encoder → LCOS 1 → LCOS 2 → LCOS 3 → QWP / PBS',.80,4.33,.225,muted)
text('Three complete SLM devices; polarization response and relay geometry require calibration.',.80,3.91,.205,muted)
line('Vertical panel rule',[(15.0,4.04),(15.0,9.16)],rule,.012)

text('c',15.45,8.99,.32,bold=True);text('Polarization coupling in each layer',15.95,8.99,.29,bold=True)
text('Effective anisotropic retarder J(θ, Γ)',15.60,8.45,.25,purple,True)
rect('LC cell pale slab',18.0,6.8,1.5,1.10,violet)
for ix in range(6):
    for iy in range(4):
        x=18.12+ix*.25;y=6.95+iy*.24;angle=.55*math.sin(ix*.7+iy)
        dx=.085*math.cos(angle);dy=.085*math.sin(angle)
        line('LC director',[(x-dx,y-dy),(x+dx,y+dy)],purple,.027)
text('θ(x,y)',18.75,6.46,.23,purple,align='CENTER')
arrow('Input LCP',(15.70,7.40),(17.75,7.40),blue,.025);text('L input',16.5,7.69,.23,blue,True,'CENTER')
arrow('Preserved LCP',(19.65,7.40),(22.10,7.90),blue,.025)
arrow('Converted RCP',(19.65,7.40),(22.10,6.85),orange,.025)
text('L preserved',22.18,7.86,.21,blue);text('R converted',22.18,6.80,.21,orange)
text('L → L:  cos(Γ/2)',15.60,5.98,.265,blue)
text('L → R:  −i sin(Γ/2) exp(+i2θ)',15.60,5.51,.265,orange)
text('R → L:  −i sin(Γ/2) exp(−i2θ)',15.60,5.04,.265,blue)
text('R → R:  cos(Γ/2)',15.60,4.57,.265,orange)
text('Partial conversion is retained when Γ ≠ π.',15.60,4.04,.215,muted)
line('Bottom panels separator',[(.65,3.52),(23.35,3.52)],rule,.012)

text('d',.65,2.98,.32,bold=True);text('Joint optimization and resolution interpretation',1.15,2.98,.29,bold=True)
text('Forward model',.80,2.35,.24,bold=True)
text('E_out = P3 J3 P2 J2 P1 J1 P0 E_in(C)',.80,1.89,.29)
text('Î_A = |E_L|²     Î_B = |E_R|²',.80,1.40,.27)
text('Train ψ and the three spatial Jones maps jointly.',.80,.95,.22,muted)
text('Reconstruction loss',9.05,2.35,.24,bold=True)
text('L = MSE(Î_A, I_A) + MSE(Î_B, I_B)',9.05,1.89,.265)
text('Evaluate on unseen image pairs and resolution targets.',9.05,1.40,.22,muted)
text('Report PSNR / SSIM and channel crosstalk.',9.05,.95,.22,muted)
text('Sampling target, same field of view',17.0,2.35,.24,bold=True)
text('24 → 96:  4× samples per axis',17.0,1.89,.27,blue,True)
text('16× output pixels per channel',17.0,1.40,.24)
text('Pixel count alone is not a resolution measurement.',17.0,.95,.215,muted)
line('Footer rule',[(.65,.61),(23.35,.61)],rule,.009)
text('Research concept. Images and phase patterns are illustrative; no measured reconstruction or diffraction-limit improvement is claimed.',.67,.27,.19,muted)

bpy.ops.object.camera_add(location=(W/2,H/2,35));camera=bpy.context.object;camera.name='Figure orthographic camera';camera.data.type='ORTHO';camera.data.ortho_scale=W;camera.rotation_euler=(0,0,0);scene.camera=camera
scene.world=bpy.data.worlds.new('Figure white world');scene.world.use_nodes=True
next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(1,1,1,1)
scene.render.engine='CYCLES';scene.cycles.device='GPU';scene.cycles.samples=16
scene.render.resolution_x=6000;scene.render.resolution_y=3750;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.film_transparent=False
scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.render.filter_size=.7
scene.render.filepath=os.path.join(OUT,'research_v005.png')
colors={m.name:'#'+''.join(f'{round((v*12.92 if v<=.0031308 else 1.055*v**(1/2.4)-.055)*255):02X}' for v in m.node_tree.nodes.get('Emission').inputs[0].default_value[:3]) for m in [ink,muted,blue,orange,purple,green] if m.node_tree.nodes.get('Emission')}
# Node names are locale-dependent, so collect display colours by node type.
colors={}
for m in [ink,muted,blue,orange,purple,green]:
    e=next(n for n in m.node_tree.nodes if n.type=='EMISSION')
    colors[m.name]='#'+''.join(f'{round((v*12.92 if v<=.0031308 else 1.055*v**(1/2.4)-.055)*255):02X}' for v in e.inputs[0].default_value[:3])
with open(os.path.join(OUT,'labels.json'),'w',encoding='utf-8') as f:json.dump({'width':W,'height':H,'labels':TEXTS,'colors':colors},f,ensure_ascii=False,indent=2)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'research_v005.blend'))
bpy.ops.render.render(write_still=True)
for o in scene.objects:
    if o.type=='FONT':o.hide_render=True
scene.render.filepath=os.path.join(OUT,'research_base.png');bpy.ops.render.render(write_still=True)
print('RESEARCH_FIGURE_COMPLETE',flush=True)
