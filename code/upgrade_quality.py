"""Create an orbit-ready Blender scene and high-resolution review images."""
import bpy, os, json
from mathutils import Vector

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,'models')
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT,'optical_system_v001.blend'))
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.samples=128
scene.cycles.use_adaptive_sampling=True
scene.cycles.adaptive_threshold=.015
scene.cycles.use_denoising=True
scene.cycles.preview_samples=24
scene.render.resolution_x=3840
scene.render.resolution_y=2880
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGB'
scene.render.image_settings.color_depth='8'
scene.render.film_transparent=False
scene.render.filter_size=.8
scene.render.use_file_extension=True
scene.render.use_simplify=False
scene.render.use_stamp=False
scene.render.image_settings.compression=25
scene.camera=bpy.data.objects['Camera overview']
scene.camera.data.dof.use_dof=False

# Use an available supported GPU, otherwise retain portable CPU rendering.
devices=[]
prefs=bpy.context.preferences.addons['cycles'].preferences
for backend in ['OPTIX','CUDA','HIP','ONEAPI','METAL']:
    try:
        prefs.compute_device_type=backend
        prefs.get_devices()
        gpu=[d for d in prefs.devices if d.type!='CPU']
        if gpu:
            for d in prefs.devices:d.use=d.type!='CPU'
            scene.cycles.device='GPU';devices=[d.name for d in gpu];break
    except Exception:pass
if not devices:scene.cycles.device='CPU'
print('RENDER_DEVICE',scene.cycles.device,devices,flush=True)

# The saved file opens in a real 3D viewport, not a static Render Result.
target=Vector((0,0,.15))
rotation=(Vector((2.6,-3.6,3.5))-target).to_track_quat('Z','Y')
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.region_3d.view_location=target
            space.region_3d.view_rotation=rotation
            space.region_3d.view_distance=3.65
            space.region_3d.view_perspective='PERSP'
            space.clip_start=.005;space.clip_end=250
            space.lens=45
            space.shading.type='MATERIAL'
            space.shading.use_scene_lights=False
            space.shading.use_scene_world=False
            space.overlay.show_overlays=False
            space.show_gizmo=True
            space.lock_camera=False
bpy.context.preferences.inputs.use_rotate_around_active=False
bpy.context.preferences.inputs.use_zoom_to_mouse=True
bpy.ops.object.select_all(action='DESELECT')
for o in scene.objects:
    if o.type in {'CAMERA','LIGHT'} or o.name=='Studio ground':
        o.hide_set(True)  # viewport only; still included in final render

# A dedicated close camera avoids enlarging a small area of an overview PNG.
bpy.ops.object.camera_add(location=(.04,-.48,.64))
detail=bpy.context.object;detail.name='Camera SLM detail'
detail.rotation_euler=(Vector((-.53,.32,.24))-detail.location).to_track_quat('-Z','Y').to_euler()
detail.data.type='ORTHO';detail.data.ortho_scale=.48;detail.data.dof.use_dof=False
detail.hide_set(True)
bpy.ops.object.select_all(action='DESELECT')
scene.camera=bpy.data.objects['Camera overview']
scene.render.filepath=os.path.join(OUT,'overview_v002_4k.png')
scene['viewing_help']='Middle mouse: orbit; wheel: zoom; Shift + middle mouse: pan. Z > Rendered for progressive scene lighting. F11 toggles render display.'
help_text=bpy.data.texts.get('VIEWING_GUIDE') or bpy.data.texts.new('VIEWING_GUIDE')
help_text.write('This is an editable 3D scene.\nMiddle mouse drag: orbit\nScroll wheel: zoom\nShift + middle mouse: pan\nZ > Material Preview: fast textured navigation\nZ > Rendered: progressive scene-light rendering\nF11: toggle static render result\nNumpad 0: active camera\n\nThe output and code textures remain illustrative.\n')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'optical_system_v002.blend'))
bpy.ops.render.render(write_still=True)
scene.camera=detail
scene.render.resolution_x=2560;scene.render.resolution_y=2560
scene.render.filepath=os.path.join(OUT,'detail_v002.png')
bpy.ops.render.render(write_still=True)
scene.camera=bpy.data.objects['Camera optical layout']
scene.render.resolution_x=3840;scene.render.resolution_y=2880
scene.render.filepath=os.path.join(OUT,'layout_v002_4k.png')
bpy.ops.render.render(write_still=True)
with open(os.path.join(OUT,'quality_v002.json'),'w',encoding='utf-8') as f:
    json.dump({'overview':[3840,2880],'layout':[3840,2880],'detail':[2560,2560],'samples':128,'denoising':True,'device':scene.cycles.device,'devices':devices,'interactive_file':'optical_system_v002.blend'},f,indent=2)
print('QUALITY_UPGRADE_COMPLETE',flush=True)
