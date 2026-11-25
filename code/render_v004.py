"""Resume renders from the saved scene and validate the orbit before encoding."""
import bpy,os,math
from mathutils import Vector
OUT=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'models')
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT,'optical_system_v004.blend'))
s=bpy.context.scene
cam=bpy.data.objects['Camera 360 orbit'];orbit=bpy.data.objects['Camera orbit - vertical Z axis']
s.frame_set(1)
cam.parent=None;cam.location=(2.9,-3.7,3.4)
cam.rotation_euler=(Vector((0,0,.17))-cam.location).to_track_quat('-Z','Y').to_euler()
bpy.context.view_layer.update();world=cam.matrix_world.copy();cam.parent=orbit;cam.matrix_world=world
bpy.context.view_layer.update()
for f in [1,49,97,145,193]:
    s.frame_set(f);bpy.context.view_layer.update()
    direction=cam.matrix_world.to_quaternion()@Vector((0,0,-1))
    err=direction.angle(Vector((0,0,.17))-cam.matrix_world.translation)
    assert err<.001,(f,err)
print('ORBIT_AIM_CHECK_OK',flush=True)
s.frame_set(1)
# Provide post mounts under the two output analyzers.
col=bpy.data.collections['10_Diagram_details'];m=bpy.data.materials['Diagram - black optical rings'];metal=bpy.data.materials['Diagram - silver optical mounts']
for name in ['Analysis waveplate 1','Analysis waveplate 2']:
    p=bpy.data.objects[name].location
    if bpy.data.objects.get(name+' support base'):continue
    bpy.ops.mesh.primitive_cube_add(size=1,location=(p.x,p.y,.062));o=bpy.context.object;o.name=name+' support base';o.dimensions=(.075,.07,.018);o.data.materials.append(m)
    bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.008,depth=.18,location=(p.x,p.y,.16));o=bpy.context.object;o.name=name+' support post';o.data.materials.append(metal)
    for poly in o.data.polygons:poly.use_smooth=len(poly.vertices)==4
bpy.ops.object.select_all(action='DESELECT')
s.camera=bpy.data.objects['Camera overview'];s.render.filepath=os.path.join(OUT,'overview_v004_4k.png')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'optical_system_v004.blend'))
bpy.ops.render.render(write_still=True)
s.camera=bpy.data.objects['Camera SLM detail'];s.render.resolution_x=2560;s.render.resolution_y=2560
s.render.filepath=os.path.join(OUT,'detail_v004.png');bpy.ops.render.render(write_still=True)
s.camera=cam;s.render.engine='CYCLES';s.cycles.samples=16;s.cycles.adaptive_threshold=.08
s.render.resolution_x=1280;s.render.resolution_y=960
s.render.image_settings.media_type='VIDEO';s.render.image_settings.file_format='FFMPEG';s.render.ffmpeg.format='MPEG4';s.render.ffmpeg.codec='H264'
s.render.ffmpeg.constant_rate_factor='HIGH';s.render.ffmpeg.ffmpeg_preset='GOOD';s.render.ffmpeg.audio_codec='NONE'
s.render.filepath=os.path.join(OUT,'orbit_v004.mp4')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'optical_orbit_v004.blend'))
print('ORBIT_START',flush=True)
bpy.ops.render.render(animation=True)
print('STYLE_AND_ORBIT_COMPLETE',flush=True)
