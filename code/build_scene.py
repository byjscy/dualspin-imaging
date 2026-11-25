"""Build an editable concept assembly; optical response is not simulated."""
import bpy, math, os, json
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'models')
os.makedirs(OUT, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name != 'Collection' and c.users == 0: bpy.data.collections.remove(c)

def collection(name):
    c=bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); return c
groups={n:collection(n) for n in ['00_Bench','01_Laser','02_Encoder','03_SLM_A','04_SLM_B','05_SLM_C','06_Output','07_LightPaths','08_Annotations','09_Studio']}
active=groups['00_Bench']
def move(o):
    for c in list(o.users_collection): c.objects.unlink(o)
    active.objects.link(o); return o
def mat(name,color,metal=0,rough=.4,emission=0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough
    if emission: p.inputs['Emission Color'].default_value=(*color,1); p.inputs['Emission Strength'].default_value=emission
    return m
black=mat('Anodized graphite',(.025,.034,.046),.7)
silver=mat('Brushed aluminium',(.42,.49,.56),.8)
dark=mat('Rubber and cables',(.009,.012,.018),0,.7)
glass=mat('LCOS reflective aperture',(.16,.25,.33),.95,.12)
green=mat('532 nm beam display',(.04,1,.25),0,.2,3)
cyan=mat('LCP channel indicator',(.02,.65,1),0,.3,2)
orange=mat('RCP channel indicator',(1,.28,.045),0,.3,2)
white=mat('Label white',(.8,.88,.94),0,.5,.1)
blue=mat('Controller blue',(.02,.12,.25),.4)

def cube(name,loc,dim,m,bevel=.003,q=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=move(bpy.context.object); o.name=name; o.dimensions=dim
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if q: o.rotation_mode='QUATERNION'; o.rotation_quaternion=q
    if m:o.data.materials.append(m)
    if bevel:
        mod=o.modifiers.new('Machined edge bevel','BEVEL'); mod.width=bevel; mod.segments=3
        o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return o
def rod(name,a,b,r,m):
    a,b=Vector(a),Vector(b); d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=r,depth=d.length,location=(a+b)/2)
    o=move(bpy.context.object);o.name=name;o.rotation_mode='QUATERNION';o.rotation_quaternion=d.to_track_quat('Z','Y');o.data.materials.append(m)
    return o
def line(name,pts,r,m):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.bevel_depth=r;cu.bevel_resolution=3
    s=cu.splines.new('POLY');s.points.add(len(pts)-1)
    for p,co in zip(s.points,pts):p.co=(*co,1)
    o=bpy.data.objects.new(name,cu);active.objects.link(o);o.data.materials.append(m);return o
def text(name,body,loc,size=.025,m=white,rotation=None):
    cu=bpy.data.curves.new(name,'FONT');cu.body=body;cu.size=size;cu.extrude=.0002;cu.align_x='CENTER'
    o=bpy.data.objects.new(name,cu);active.objects.link(o);o.location=loc;cu.materials.append(m)
    if rotation:o.rotation_euler=rotation
    return o
def stand(name,p):
    x,y,z=p;cube(name+' foot',(x,y,.062),(.13,.105,.018),black)
    rod(name+' post',(x,y,.07),(x,y,z-.04),.012,silver)
    rod(name+' collar',(x,y,.09),(x,y,.14),.018,black)
def frame(p,n): return Vector(n).normalized().to_track_quat('Z','Y')
def panel(name,p,n,w,h,material):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata([(-w/2,-h/2,0),(w/2,-h/2,0),(w/2,h/2,0),(-w/2,h/2,0)],[],[(0,1,2,3)]);mesh.update()
    uv=mesh.uv_layers.new(name='UVMap')
    for loop,co in zip(uv.data,[(0,0),(1,0),(1,1),(0,1)]):loop.uv=co
    o=bpy.data.objects.new(name,mesh);active.objects.link(o);o.location=p;o.rotation_mode='QUATERNION';o.rotation_quaternion=frame(p,n);mesh.materials.append(material);return o

# Real-sized tabletop assembly, dimensions in metres.
cube('Optical breadboard',(0,.06,.025),(2.7,1.75,.05),silver,.012)
verts=[];faces=[]
for ix in range(53):
    for iy in range(34):
        x=-1.3+ix*.05;y=-.76+iy*.05
        start=len(verts)
        verts.extend((x+.003*math.cos(k*math.tau/12),y+.003*math.sin(k*math.tau/12),.0508) for k in range(12))
        faces.append(tuple(range(start,start+12)))
mesh=bpy.data.meshes.new('Mounting grid');mesh.from_pydata(verts,[],faces);mesh.update()
o=bpy.data.objects.new('Breadboard mounting grid 50 mm (visual)',mesh);active.objects.link(o);mesh.materials.append(dark)

Z=.30
P=[Vector(v) for v in [(-1.02,-.45,Z),(-.53,-.45,Z),(-.53,.32,Z),(.03,-.17,Z),(.55,.34,Z),(.89,-.22,Z)]]
active=groups['01_Laser']
cube('532 nm laser head',(-1.12,-.45,Z),(.25,.105,.095),black)
stand('Laser mount',(-1.12,-.45,Z))
rod('Laser emission barrel',(-1.02,-.45,Z),(-.96,-.45,Z),.027,silver)
cube('Laser PSU',(-1.10,-.70,.10),(.23,.15,.09),black)
for i in range(7):cube('Cooling fin',(-1.21+i*.03,-.45,Z+.05),(.008,.10,.008),silver,.001)

# Device planes are oriented by reflection bisectors rather than arbitrary tilts.
def device(i,key,name,width=.18,height=.14):
    global active
    active=groups[key];p=P[i];vin=(p-P[i-1]).normalized();vout=(P[i+1]-p).normalized();n=(vout-vin).normalized();q=frame(p,n)
    def local(v):return p+q@Vector(v)-n*.012
    body=cube(name+' complete housing',local((0,0,-.034)),(width,height,.065),black,.008,q)
    body['reference']='FSLM-2K73 series visual approximation; housing dimensions unverified'
    body['optical_model']='Concept fold path; no Jones/LCOS response validation'
    cube(name+' faceplate',local((0,0,.001)),(width*.92,height*.9,.008),silver,.004,q)
    cube(name+' aperture bezel',local((0,0,.007)),(.052,.052,.008),black,.003,q)
    aperture=panel(name+' 13.1 mm active aperture',local((0,0,.012)),n,.0131,.0131,glass)
    aperture['active_area_m']=.0131
    for x in [-width*.37,width*.37]:
        for y in [-height*.34,height*.34]:
            cube(name+' captive screw',local((x,y,.008)),(.006,.006,.003),dark,.001,q)
    for k in range(6):cube(name+' ventilation slot',local((width*.32,-.025+k*.01,-.069)),(.045,.003,.002),dark,.0005,q)
    stand(name+' adjustable mount',p)
    controller=(p.x,p.y+.17,.095)
    cube(name+' driver enclosure',controller,(.19,.105,.07),blue)
    cube(name+' HDMI connector',(controller[0]+.065,controller[1]-.055,.10),(.026,.009,.012),silver,.001)
    line(name+' driver cable',[local((width*.4,0,-.05)),(p.x+.13,p.y,.13),(p.x+.13,p.y+.16,.09),controller],.003,dark)
    return n
nenc=device(1,'02_Encoder','ENCODER',.22,.17)
for i,k in [(2,'03_SLM_A'),(3,'04_SLM_B'),(4,'05_SLM_C')]:device(i,k,'SLM '+str(i-1))

# Self-contained illustrative textures: hand-drawn-like digits and a 24x24 code.
def texture(name,n,kind):
    im=bpy.data.images.new(name,width=n,height=n,alpha=False)
    segs={3:[(.22,.82,.75,.82),(.75,.82,.61,.52),(.33,.50,.66,.50),(.66,.5,.77,.23),(.77,.23,.26,.18)],7:[(.2,.82,.8,.82),(.8,.82,.39,.15)]}
    pix=[]
    for y in range(n):
        for x in range(n):
            u,v=(x+.5)/n,(y+.5)/n
            if kind=='code': val=((x*17+y*31+(x*y*7)%43)%61)/60
            else:
                ds=[]
                for ax,ay,bx,by in segs[kind]:
                    dx,dy=bx-ax,by-ay;t=max(0,min(1,((u-ax)*dx+(v-ay)*dy)/(dx*dx+dy*dy)))
                    ds.append(math.hypot(u-ax-t*dx,v-ay-t*dy))
                val=max(0,min(1,(.058-min(ds))*n/2))
            pix.extend((val,val,val,1))
    im.pixels=pix;im.filepath_raw=os.path.join(OUT,name+'.png');im.file_format='PNG';im.save();im.pack()
    m=mat(name,(1,1,1));nt=m.node_tree;p=nt.nodes.get('Principled BSDF');t=nt.nodes.new('ShaderNodeTexImage');t.image=im;t.interpolation='Closest'
    nt.links.new(t.outputs['Color'],p.inputs['Base Color']);nt.links.new(t.outputs['Color'],p.inputs['Emission Color']);p.inputs['Emission Strength'].default_value=.7
    return m
a=texture('input_3_96',96,3);b=texture('input_7_96',96,7);code=texture('code_24_demo',24,'code')
active=groups['02_Encoder']
# Encoding display inset uses the physical 13.1 mm aperture; diagram is enlarged on monitor.
p=P[1]+nenc*.00005;panel('24x24 electronic code on reflective display',p,nenc,.0131,.0131,code)
q=frame((0,0,0),(0,-1,0))
cube('Encoding workstation monitor',(-.99,.51,.39),(.48,.27,.025),black,.008,q)
panel('Input image A',(-1.13,.493,.40),(0,-1,0),.115,.115,a)
panel('Input image B',(-.99,.493,.40),(0,-1,0),.115,.115,b)
panel('Encoded electronic pattern',(-.84,.493,.40),(0,-1,0),.115,.115,code)
stand('Workstation monitor',(-.99,.51,.30))
text('Monitor caption','96 x 96     96 x 96     24 x 24',(-.99,.475,.30),.016,white,(math.pi/2,0,0))

active=groups['06_Output']
split=P[5]
cube('Polarization analyzer mount',split,(.10,.10,.10),black)
stand('Analyzer support',split)
cube('PBS cube visual',split+Vector((0,0,.055)),(.055,.055,.012),glass)
analysis_point=P[4].lerp(split,.75)
analysis_normal=(P[4]-split).normalized()
panel('Common quarter-wave analysis plate before PBS',analysis_point,analysis_normal,.065,.065,glass)
stand('Common quarter-wave plate mount',analysis_point)
ends=[Vector((1.16,-.22,Z)),Vector((.89,-.64,Z))]
for j,(end,m,im) in enumerate(zip(ends,[cyan,orange],[a,b])):
    n=(split-end).normalized();q=frame(end,n)
    cube('Output '+str(j+1)+' receiver',end-n*.01,(.17,.15,.025),black,.004,q)
    panel('Output '+str(j+1)+' illustrative reconstruction',end+n*.006,n,.125,.115,im)
    stand('Output '+str(j+1),end)
    # Quarter-wave analysis plate placed on each branch.
    mid=split.lerp(end,.5)
    panel('Analysis waveplate '+str(j+1),mid,n,.055,.055,glass)

cube('Dual output readout monitor',(.99,.55,.40),(.37,.23,.025),black,.007,frame((0,0,0),(0,-1,0)))
panel('Readout image A',(.90,.533,.42),(0,-1,0),.14,.14,a)
panel('Readout image B',(1.075,.533,.42),(0,-1,0),.14,.14,b)
stand('Dual output readout',(.99,.55,.30))
text('Readout labels','LCP / A       RCP / B',(.99,.52,.32),.018,white,(math.pi/2,0,0))

active=groups['07_LightPaths']
for i in range(len(P)-1):rod('Incident / reflected path '+str(i+1),P[i],P[i+1],.0016,green)
for e,m in zip(ends,[cyan,orange]):rod('Polarization resolved output',split,e,.0018,m)
# Input polarization preparation along first beam segment.
active=groups['01_Laser']
for x,label in [(-.87,'Polarizer'),(-.73,'Preparation waveplate')]:
    p=(x,-.45,Z);panel(label,p,(1,0,0),.06,.06,glass);stand(label,p)

active=groups['08_Annotations']
text('Scene title','POLARIZATION IMAGE DECODER',(.0,.80,.065),.055,black)
text('Scene subtitle','REFLECTIVE ENCODER  /  THREE LCOS DEVICES  /  DUAL OUTPUT',(.0,.735,.065),.020,black)
labels=[('532 nm LASER',(-1.10,-.58,.065)),('ENCODER 24 x 24',(-.53,-.60,.065)),('SLM 01',(-.53,.18,.065)),('SLM 02',(.03,-.32,.065)),('SLM 03',(.55,.19,.065)),('POLARIZATION ANALYZER',(1.0,-.08,.065)),('LCP / IMAGE A',(1.13,-.37,.065)),('RCP / IMAGE B',(.89,-.77,.065))]
for title,loc in labels:text(title,title,loc,.022,black)
text('Concept notice','CONCEPT ASSEMBLY | DEMO IMAGE TEXTURES | MECHANICAL DIMENSIONS APPROXIMATE',(.0,-.83,.065),.019,black)

active=groups['09_Studio']
floor=mat('Studio floor',(.025,.035,.055),.1,.65)
cube('Studio ground',(0,0,-.06),(200,200,.05),floor,0)
def camera(name,loc,target,scale):
    bpy.ops.object.camera_add(location=loc);o=move(bpy.context.object);o.name=name;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();o.data.type='ORTHO';o.data.ortho_scale=scale;return o
cam=camera('Camera overview',(2.6,-3.6,3.5),(0,0,.13),3.6)
top=camera('Camera optical layout',(0,0,4),(0,0,0),3.1)
for name,loc,power,size in [('Key',(0,-1,4),450,4),('Fill',(-2,1,2),250,3),('Rim',(2,2,3),350,3)]:
    bpy.ops.object.light_add(type='AREA',location=loc);o=move(bpy.context.object);o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
scene=bpy.context.scene;scene.camera=cam;scene.render.engine='CYCLES';scene.cycles.samples=32
scene.render.resolution_x=1800;scene.render.resolution_y=1400;scene.render.resolution_percentage=100
scene.world.color=(.18,.18,.18);scene.view_settings.view_transform='AgX';scene.unit_settings.system='METRIC'
scene['status']='Concept equipment model; not validated optical reconstruction'
scene['reference_notes']='Three complete reflective 2K73-series inspired devices. PDF geometric-phase model is not assumed equivalent to commercial LCOS.'
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':area.spaces.active.region_3d.view_distance=3.8
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'optical_system_v001.blend'))
scene.render.filepath=os.path.join(OUT,'overview_v001.png');bpy.ops.render.render(write_still=True)
scene.camera=top;scene.render.filepath=os.path.join(OUT,'layout_v001.png');bpy.ops.render.render(write_still=True)
scene.camera=cam
report={'blender':bpy.app.version_string,'slm_count':3,'units':'metres','active_aperture_m':.0131,'textures':'Illustrative, not trained or simulated','reflection_check':[]}
for i in range(1,5):
    vi=(P[i]-P[i-1]).normalized();vo=(P[i+1]-P[i]).normalized();n=(vo-vi).normalized();r=vi-2*vi.dot(n)*n
    report['reflection_check'].append({'device':i,'direction_error':(r-vo).length})
report['objects']=len(scene.objects)
with open(os.path.join(OUT,'validation_v001.json'),'w',encoding='utf-8') as f:json.dump(report,f,indent=2)
print('BUILD_COMPLETE',json.dumps(report))
