"""Correct the 12 mm head/surface offset so beams meet at aperture centres."""
import bpy, os, json
from mathutils import Vector
OUT=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'models')
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT,'optical_system_v002.blend'))
keys=['02_Encoder','03_SLM_A','04_SLM_B','05_SLM_C']
parts=['complete housing','faceplate','aperture bezel','active aperture','captive screw','ventilation slot']
report=[]
paths=[bpy.data.objects['Incident / reflected path '+str(i)] for i in range(1,6)]
def ends(o):
    zs=[v.co.z for v in o.data.vertices]
    return [o.matrix_world@Vector((0,0,z)) for z in [min(zs),max(zs)]]
bpy.context.view_layer.update()
for key in keys:
    col=bpy.data.collections[key]
    aperture=next(o for o in col.objects if 'active aperture' in o.name)
    normal=aperture.rotation_quaternion@Vector((0,0,1))
    old=aperture.location.copy()
    for o in col.objects:
        if any(part in o.name for part in parts):o.location-=normal*.012
    if key=='02_Encoder':
        bpy.data.objects['24x24 electronic code on reflective display'].location-=normal*.01345
    center=aperture.location.copy()
    # Find adjacent beam endpoints closest to the corrected aperture centre.
    nearby=[]
    for beam in paths:
        ep=min(ends(beam),key=lambda p:(p-center).length)
        if (ep-center).length<.01:nearby.append((beam.name,(ep-center).length))
    assert len(nearby)==2,(key,nearby)
    assert max(err for _,err in nearby)<1e-6
    report.append({'device':key,'centre':list(center),'surface_shift_m':(old-center).length,'beam_endpoint_errors_m':nearby})
bpy.context.view_layer.update()
scene=bpy.context.scene
scene.camera=bpy.data.objects['Camera overview']
scene.render.resolution_x=3840;scene.render.resolution_y=2880
scene.render.filepath=os.path.join(OUT,'overview_v003_4k.png')
scene['alignment_fix']='Device head translated 12 mm so reflective aperture coincides with both beam endpoints.'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'optical_system_v003.blend'))
with open(os.path.join(OUT,'alignment_v003.json'),'w',encoding='utf-8') as f:json.dump(report,f,indent=2)
print('ALIGNMENT_CHECK_OK',json.dumps(report),flush=True)
scene.camera=bpy.data.objects['Camera SLM detail']
scene.render.resolution_x=2560;scene.render.resolution_y=2560
scene.render.filepath=os.path.join(OUT,'detail_v003.png')
bpy.ops.render.render(write_still=True)
scene.camera=bpy.data.objects['Camera overview']
scene.render.resolution_x=3840;scene.render.resolution_y=2880
scene.render.filepath=os.path.join(OUT,'overview_v003_4k.png')
bpy.ops.render.render(write_still=True)
print('CENTERING_COMPLETE',flush=True)
