"""Render the validated orbit saved in the scientific diagram model."""
import bpy,os
OUT=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'models')
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT,'optical_system_v004.blend'))
s=bpy.context.scene;s.camera=bpy.data.objects['Camera 360 orbit'];s.frame_set(1)
s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=16;s.cycles.adaptive_threshold=.08
s.render.resolution_x=1280;s.render.resolution_y=960;s.render.resolution_percentage=100
s.render.image_settings.media_type='VIDEO';s.render.image_settings.file_format='FFMPEG'
s.render.ffmpeg.format='MPEG4';s.render.ffmpeg.codec='H264';s.render.ffmpeg.constant_rate_factor='HIGH'
s.render.ffmpeg.ffmpeg_preset='GOOD';s.render.ffmpeg.audio_codec='NONE'
s.render.filepath=os.path.join(OUT,'orbit_v004.mp4')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'optical_orbit_v004.blend'))
bpy.ops.render.render(animation=True)
print('ORBIT_COMPLETE',flush=True)
