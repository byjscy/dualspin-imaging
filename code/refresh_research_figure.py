import bpy,os,json
from mathutils import Vector,Quaternion
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,'models','figure')
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT,'research_v005.blend'))
s=bpy.data.scenes['02_Research_figure'];bpy.context.window.scene=s
replace={'J₁     J₂     J₃':'J1     J2     J3','E_out = P₃ J₃ P₂ J₂ P₁ J₁ P₀ E_in(C)':'E_out = P3 J3 P2 J2 P1 J1 P0 E_in(C)'}
for o in s.objects:
    if o.type=='FONT':o.data.body=replace.get(o.data.body,o.data.body);o.hide_render=False
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            v=area.spaces.active;v.region_3d.view_location=(12,7.5,0);v.region_3d.view_rotation=Quaternion((1,0,0,0));v.region_3d.view_distance=22;v.region_3d.view_perspective='CAMERA';v.shading.type='MATERIAL';v.overlay.show_overlays=False
p=os.path.join(OUT,'labels.json');d=json.load(open(p,encoding='utf-8'))
for l in d['labels']:l['text']=replace.get(l['text'],l['text'])
with open(p,'w',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
s.render.filepath=os.path.join(OUT,'research_v005.png')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'research_v005.blend'))
bpy.ops.render.render(write_still=True)
print('RESEARCH_LABELS_UPDATED',flush=True)
