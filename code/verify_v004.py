"""Check centred beams and representative orbit viewpoints."""
import bpy,os,json
from mathutils import Vector
OUT=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'models')
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT,'optical_system_v004.blend'))
s=bpy.context.scene;bpy.context.view_layer.update()
beam_objects=list(bpy.data.collections['07_LightPaths'].objects)
report=[]
for group in ['02_Encoder','03_SLM_A','04_SLM_B','05_SLM_C']:
    ap=next(o for o in bpy.data.collections[group].objects if 'active aperture' in o.name)
    nearby=[]
    for o in beam_objects:
        if o.type!='MESH' or not o.name.startswith('Incident'):continue
        zs=[v.co.z for v in o.data.vertices]
        error=min((o.matrix_world@Vector((0,0,z))-ap.location).length for z in [min(zs),max(zs)])
        if error<1e-6:nearby.append(o.name)
    assert len(nearby)==2,(group,nearby)
    report.append({'group':group,'aligned_beams':nearby})
cam=bpy.data.objects['Camera 360 orbit'];s.camera=cam
s.render.resolution_x=960;s.render.resolution_y=720;s.cycles.samples=16
for frame in [1,49,97,145]:
    s.frame_set(frame);bpy.context.view_layer.update()
    assert (cam.matrix_world.to_quaternion()@Vector((0,0,-1))).angle(Vector((0,0,.17))-cam.matrix_world.translation)<.001
    s.render.filepath=os.path.join(OUT,'orbit_check_'+str(frame)+'.png');bpy.ops.render.render(write_still=True)
with open(os.path.join(OUT,'validation_v004.json'),'w',encoding='utf-8') as f:json.dump({'aligned_devices':report,'orbit_checked_frames':[1,49,97,145],'rotation_degrees':360,'physical_reconstruction':False},f,indent=2)
print('V004_VERIFIED',flush=True)
