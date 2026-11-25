"""Scientific optical-layout styling and a full 360-degree camera orbit."""
import bpy, math, os, json, sys
from mathutils import Vector
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,'models')
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT,'optical_system_v003.blend'))
scene=bpy.context.scene
def material(name,c,metal=0,rough=.35,emit=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*c,1)
    p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
    p.inputs['Emission Color'].default_value=(*c,1);p.inputs['Emission Strength'].default_value=emit
    return m
ivory=material('Diagram - satin pearl platform',(.68,.70,.68),.25,.48)
ink=material('Diagram - lettering',(.025,.065,.075),.05,.4)
teal=material('Diagram - teal instrument trim',(.025,.24,.27),.6,.27)
steel=material('Diagram - silver optical mounts',(.45,.54,.56),.8,.28)
ringmat=material('Diagram - black optical rings',(.018,.033,.037),.65,.28)
beam=material('Diagram - vivid green beam',(.08,.85,.015),0,.25,2.3)
left=material('Diagram - LCP cyan beam',(.0,.55,.9),0,.25,2.0)
right=material('Diagram - RCP amber beam',(.95,.20,.015),0,.25,2.0)
optic=material('Diagram - tinted optical glass',(.12,.55,.67),.1,.12)
p=next(n for n in optic.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Transmission Weight'].default_value=.65;p.inputs['IOR'].default_value=1.45
bpy.data.objects['Optical breadboard'].data.materials[0]=ivory
bpy.data.materials['Studio floor'].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.43,.39,.34,1)
for name in ['Anodized graphite','Controller blue']:
    p=bpy.data.materials[name].node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value=(.018,.045,.05,1) if name.startswith('Anodized') else (.025,.12,.14,1)
for o in bpy.data.collections['08_Annotations'].objects:
    if o.type=='FONT':o.data.materials.clear();o.data.materials.append(ink)
bpy.data.objects['Scene title'].data.body='DUAL-CHANNEL IMAGE RECONSTRUCTION'
bpy.data.objects['Scene title'].data.size=.043
bpy.data.objects['Scene subtitle'].data.body='ELECTRONIC ENCODING   /   THREE REFLECTIVE LCOS STAGES   /   POLARIZATION READOUT'
bpy.data.objects['Scene subtitle'].data.size=.016

col=bpy.data.collections.new('10_Diagram_details');scene.collection.children.link(col)
def add(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    col.objects.link(o);return o
def cube(name,p,d,m,q=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=p);o=add(bpy.context.object);o.name=name;o.dimensions=d
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if q:o.rotation_mode='QUATERNION';o.rotation_quaternion=q
    o.data.materials.append(m);b=o.modifiers.new('Rounded machined edges','BEVEL');b.width=.0015;b.segments=3
    o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');return o
def torus(name,p,q,major=.034,minor=.004,m=ringmat):
    bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=64,minor_segments=12,location=p)
    o=add(bpy.context.object);o.name=name;o.rotation_mode='QUATERNION';o.rotation_quaternion=q;o.data.materials.append(m)
    for f in o.data.polygons:f.use_smooth=True
    return o
def label(name,body,p,q,size=.010,m=ink):
    cu=bpy.data.curves.new(name,'FONT');cu.body=body;cu.align_x='CENTER';cu.size=size;cu.extrude=.00005
    o=bpy.data.objects.new(name,cu);col.objects.link(o);o.location=p;o.rotation_mode='QUATERNION';o.rotation_quaternion=q;cu.materials.append(m);return o

# Preserve vertex positions exactly while increasing visible beam diameter.
beam_report=[]
paths=list(bpy.data.collections['07_LightPaths'].objects)
for o in paths:
    if o.type!='MESH':continue
    r=.004 if o.name.startswith('Incident') else .0038
    for v in o.data.vertices:
        radial=math.hypot(v.co.x,v.co.y)
        if radial>1e-9:v.co.x*=r/radial;v.co.y*=r/radial
    color=beam if o.name.startswith('Incident') else left if o.data.materials[0].name.startswith('LCP') else right
    o.data.materials.clear();o.data.materials.append(color)
    for poly in o.data.polygons:poly.use_smooth=len(poly.vertices)==4
    zs=[v.co.z for v in o.data.vertices]
    a=o.matrix_world@Vector((0,0,min(zs)));b=o.matrix_world@Vector((0,0,max(zs)))
    mid=a.lerp(b,.58);direction=(b-a).normalized()
    bpy.ops.mesh.primitive_cone_add(vertices=32,radius1=.010,radius2=0,depth=.032,location=mid)
    arrow=add(bpy.context.object);arrow.name='Propagation arrow - '+o.name
    arrow.rotation_mode='QUATERNION';arrow.rotation_quaternion=direction.to_track_quat('Z','Y');arrow.data.materials.append(color)
    beam_report.append({'name':o.name,'diameter_m':2*r,'endpoints':[list(a),list(b)]})

# Round, post-mounted waveplates are a familiar visual cue in optical diagrams.
plate_names=['Polarizer','Preparation waveplate','Common quarter-wave analysis plate before PBS','Analysis waveplate 1','Analysis waveplate 2']
for name in plate_names:
    plate=bpy.data.objects[name];p=plate.location.copy();q=plate.rotation_quaternion.copy()
    mesh=bpy.data.meshes.new(name+' round glass')
    mesh.from_pydata([(.028*math.cos(i*math.tau/64),.028*math.sin(i*math.tau/64),0) for i in range(64)],[],[tuple(range(64))]);mesh.update();plate.data=mesh;mesh.materials.append(optic)
    torus(name+' calibrated mount',p,q)
    torus(name+' trim',p+q@Vector((0,0,.004)),q,.030,.0015,teal)
    if name.startswith('Analysis waveplate'):
        cube(name+' support base',(p.x,p.y,.062),(.075,.07,.018),ringmat)
        bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.008,depth=.18,location=(p.x,p.y,.16))
        post=add(bpy.context.object);post.name=name+' support post';post.data.materials.append(steel)
    for k in range(12):
        angle=k*math.tau/12
        local=Vector((.035*math.cos(angle),.035*math.sin(angle),.0045))
        cube(name+' scale tick',p+q@local,(.001,.003,.0005),steel,q)

# Add recognizable instrument badges, stage adjusters, and front-panel controls.
for i,key in enumerate(['02_Encoder','03_SLM_A','04_SLM_B','05_SLM_C']):
    group=bpy.data.collections[key]
    ap=next(o for o in group.objects if 'active aperture' in o.name)
    q=ap.rotation_quaternion;p=ap.location
    cube(key+' teal nameplate',p+q@Vector((0,-.048,-.002)),(.11,.021,.002),teal,q)
    label(key+' face label','ENCODER' if i==0 else 'SLM 0'+str(i),p+q@Vector((0,-.052,-.0008)),q,.011,bpy.data.materials['Label white'])
    for x in [-.055,.055]:
        cube(key+' adjustment knob',p+q@Vector((x,.055,-.035)),(.014,.014,.025),ringmat,q)
    driver=next(o for o in group.objects if 'driver enclosure' in o.name)
    for k in range(5):cube(key+' driver cooling slot',driver.location+Vector((-.06+k*.018,0,.036)),(.008,.065,.001),ringmat)
    # Correct cable attachment to match the translated optical head from v003.
    cable=next(o for o in group.objects if 'driver cable' in o.name)
    first=cable.data.splines[0].points[0]
    v=Vector(first.co[:3])-(q@Vector((0,0,.012)));first.co=(*v,1)

# Make the analyzer visibly an optical cube rather than a solid obstruction.
pbs=bpy.data.objects['Polarization analyzer mount'];pbs.dimensions=(.085,.085,.018);pbs.location.z=.255
crystal=bpy.data.objects['PBS cube visual'];crystal.location.z=.30;crystal.dimensions=(.048,.048,.048)
crystal.data.materials.clear();crystal.data.materials.append(optic)

# Smooth circular posts; retain flat end caps.
for o in scene.objects:
    if o.type=='MESH' and any(s in o.name for s in [' post',' collar','barrel']):
        for f in o.data.polygons:f.use_smooth=len(f.vertices)==4

# Ground legends keep the setup readable from the still-image viewpoint.
q=Vector((0,0,1)).to_track_quat('Z','Y')
label('Encoding stage note','2 x 96 x 96  >  24 x 24',(-.99,.69,.067),q,.019)
label('Readout stage note','LCP / A       RCP / B',(.99,.70,.067),q,.019)
label('Beam legend','532 nm',(-.82,-.51,.067),q,.021)

# Warm studio illumination, without changing the optical route.
for o in scene.objects:
    if o.type=='LIGHT':
        o.data.color=(1,.94,.86) if o.name=='Key' else (.83,.93,1) if o.name=='Fill' else (1,1,1)
scene.world.color=(.24,.24,.24)
scene.render.engine='CYCLES';scene.cycles.device='GPU';scene.cycles.samples=128
scene.cycles.use_denoising=True;scene.cycles.denoiser='OPTIX'
scene.render.resolution_x=3840;scene.render.resolution_y=2880;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.camera=bpy.data.objects['Camera overview']
scene.camera.data.ortho_scale=3.5
scene.render.filepath=os.path.join(OUT,'overview_v004_4k.png')

# Orbit the camera, leaving the apparatus and optical alignment unchanged.
orbit=bpy.data.objects.new('Camera orbit - vertical Z axis',None);col.objects.link(orbit);orbit.location=(0,0,.17)
bpy.ops.object.camera_add(location=(2.9,-3.7,3.4));cam=add(bpy.context.object);cam.name='Camera 360 orbit'
cam.rotation_euler=(Vector((0,0,.17))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=3.65
bpy.context.view_layer.update()
world=cam.matrix_world.copy();cam.parent=orbit;cam.matrix_world=world
orbit.rotation_euler.z=0;orbit.keyframe_insert(data_path='rotation_euler',index=2,frame=1)
orbit.rotation_euler.z=math.tau;orbit.keyframe_insert(data_path='rotation_euler',index=2,frame=193)
action=orbit.animation_data.action
for layer in action.layers:
    for strip in layer.strips:
        bag=strip.channelbag(orbit.animation_data.action_slot)
        if bag:
            for fc in bag.fcurves:
                for kp in fc.keyframe_points:kp.interpolation='LINEAR'
scene.frame_start=1;scene.frame_end=192;scene.render.fps=24;scene.frame_set(1)
scene['version_notes']='v004: 8 mm diagram beams, direction arrows, circular optical mounts, clearer styling and full Z-axis camera orbit. Demonstration images remain illustrative.'
cam.hide_set(True)
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'optical_system_v004.blend'))
with open(os.path.join(OUT,'style_v004.json'),'w',encoding='utf-8') as f:json.dump({'beam_geometry':beam_report,'orbit':{'axis':'Z','frames':192,'fps':24,'duration_s':8},'reference':'User-provided optical-layout screenshots; hardware scene is editable geometry, not an AI image.'},f,indent=2)
print('STYLE_SAVED',flush=True)
bpy.ops.render.render(write_still=True)
scene.camera=bpy.data.objects['Camera SLM detail'];scene.render.resolution_x=2560;scene.render.resolution_y=2560
scene.render.filepath=os.path.join(OUT,'detail_v004.png');bpy.ops.render.render(write_still=True)

# Lower-sample GPU Cycles render for an affordable orbit animation.
scene.camera=cam;scene.render.engine='CYCLES'
scene.cycles.samples=16;scene.cycles.adaptive_threshold=.08
scene.render.resolution_x=1280;scene.render.resolution_y=960
scene.render.image_settings.media_type='VIDEO';scene.render.image_settings.file_format='FFMPEG';scene.render.ffmpeg.format='MPEG4';scene.render.ffmpeg.codec='H264'
scene.render.ffmpeg.constant_rate_factor='HIGH';scene.render.ffmpeg.ffmpeg_preset='GOOD'
scene.render.ffmpeg.audio_codec='NONE'
scene.render.filepath=os.path.join(OUT,'orbit_v004.mp4')
# Save animation configuration separately so opening the main file retains HQ still settings.
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'optical_orbit_v004.blend'))
print('ORBIT_START',flush=True)
bpy.ops.render.render(animation=True)
print('STYLE_AND_ORBIT_COMPLETE',flush=True)
