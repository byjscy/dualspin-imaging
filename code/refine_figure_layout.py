"""Fit the hardware render without clipping, and separate the caption."""
import bpy,os,json
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)));OUT=os.path.join(ROOT,'models','figure')
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT,'research_v005.blend'))
src=bpy.data.scenes['01_Reflective_apparatus'];bpy.context.window.scene=src;cam=src.camera
src.render.resolution_x=3000;src.render.resolution_y=900
q=cam.matrix_world.to_quaternion();right=q@Vector((1,0,0));up=q@Vector((0,1,0))
xs=[];ys=[]
for o in src.objects:
    if o.hide_render or o.type not in {'MESH','CURVE','FONT'}:continue
    for co in o.bound_box:
        p=o.matrix_world@Vector(co)-cam.location;xs.append(p.dot(right));ys.append(p.dot(up))
cx=(min(xs)+max(xs))/2;cy=(min(ys)+max(ys))/2
cam.location+=cx*right+cy*up
cam.data.ortho_scale=max(max(xs)-min(xs),(max(ys)-min(ys))*3000/900)*1.12
src.render.filepath=os.path.join(OUT,'apparatus.png');bpy.ops.render.render(write_still=True)
projected={}
for key,tag in [('02_Encoder','Encoding SLM'),('03_SLM_A','LCOS 1'),('04_SLM_B','LCOS 2'),('05_SLM_C','LCOS 3')]:
    o=next(o for o in bpy.data.collections[key].objects if 'active aperture' in o.name)
    p=world_to_camera_view(src,cam,o.location);projected[tag]=[p.x,p.y]
s=bpy.data.scenes['02_Research_figure'];bpy.context.window.scene=s
asset=s.objects['Editable hardware render']
for v,co in zip(asset.data.vertices,[(.65,4.50,.025),(14.65,4.50,.025),(14.65,8.70,.025),(.65,8.70,.025)]):v.co=co
im=next(i for i in bpy.data.images if os.path.basename(i.filepath)=='apparatus.png')
if im.packed_file:im.unpack(method='REMOVE')
im.filepath=os.path.join(OUT,'apparatus.png');im.reload();im.pack()
d=json.load(open(os.path.join(OUT,'labels.json'),encoding='utf-8'))
for name,(u,v) in projected.items():
    x=.65+14*u;y=4.5+4.2*v;ty=y+.33
    o=next(o for o in s.objects if o.type=='FONT' and o.data.body==name);o.location.x=x;o.location.y=ty
    leader=s.objects['Leader '+name].data.splines[0]
    leader.points[0].co=(x,ty-.05,.04,1);leader.points[1].co=(x,y+.08,.04,1)
    for l in d['labels']:
        if l['text']==name:l['x']=x;l['baseline']=ty
for l in d['labels']:
    if l['text'].startswith('532 nm laser'):
        l['size']=.205
        next(o for o in s.objects if o.type=='FONT' and o.data.body==l['text']).data.size=.205
with open(os.path.join(OUT,'labels.json'),'w',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
for o in s.objects:
    if o.type=='FONT':o.hide_render=False
s.render.filepath=os.path.join(OUT,'research_v005.png');bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'research_v005.blend'))
bpy.ops.render.render(write_still=True)
for o in s.objects:
    if o.type=='FONT':o.hide_render=True
s.render.filepath=os.path.join(OUT,'research_base.png');bpy.ops.render.render(write_still=True)
print('FIGURE_LAYOUT_REFINED',flush=True)
