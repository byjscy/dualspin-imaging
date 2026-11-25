# Optical system model

Run with the installed Blender:

```powershell
& 'D:\steam\steamapps\common\Blender\blender.exe' --background --factory-startup --python 'D:\srdd\code\build_scene.py'
```

Outputs are written to `../models`. The scene uses metres, named collections,
three complete reflective SLM assemblies, an independent reflective encoder,
input polarization preparation, and two output receivers.

The 13.1 mm square apertures reference the 2K73 series. Housing dimensions,
mounts, driver enclosures and interfaces are illustrative approximations, not
manufacturer CAD. The 50 mm table grid is for visualization.

The 96x96 digits are procedurally drawn examples, not MNIST samples. The 24x24
pattern is a demonstration texture, not a trained electronic encoder. Output
images reuse the example inputs to communicate the intended result; they are
not reconstructed optical simulation results.

The commercial LCOS device is not assumed to realize the geometric-phase
Jones matrix in the supplied PDF. Polarization response, reflection handedness,
waveplate settings, relay optics, imaging distances and reconstruction must be
validated in a separate optical design stage. Blender ray displays only show
the conceptual route. Surface normals obey specular reflection at the encoder
and the three SLMs; numerical residuals are recorded in validation_v001.json.

All image textures are packed into the blend file and also exported as PNG.

## Version 002: viewing and render quality

Run `upgrade_quality.py` with Blender after building version 001. It creates
`optical_system_v002.blend` with an orbit-ready material preview viewport,
3840x2880 output, 128 adaptive Cycles samples, denoising and a dedicated detail
camera. It renders overview, layout and a 2560x2560 close-up. It selects a
supported GPU when available. The original version is preserved.

Rotate with middle mouse, zoom with the wheel and pan with Shift + middle
mouse. Use Z > Rendered for progressive rendering while rotating. F11 toggles
the static render window; a PNG itself cannot be rotated. See
`../models/viewing_guide.txt` for Chinese instructions.

## Version 003: centred reflection points

Run `center_beams.py` after version 002. It aligns the encoder and all three
SLM reflective apertures with the beam vertices by correcting the original
12 mm surface offset. It preserves version 002, GPU settings and viewport
navigation, and writes the corrected scene, close-up, overview and numerical
endpoint checks. The base build script also includes this geometry correction.

## Version 004: scientific optical-layout style and animation

`style_v004.py` adds thicker 8 mm diagram beams, direction arrows, circular
waveplate mounts, instrument nameplates, adjustment knobs and a warm studio
presentation. This visual beam diameter is deliberately exaggerated for clarity.
Three complete SLMs and the aligned reflective endpoints are preserved.

`render_v004.py` resumes from the saved model, validates the orbit-camera aim at
four quadrants and the closing frame, adds output-analyzer supports, and renders
updated stills and video. `animate_v004.py` exports only the orbit animation.

- `optical_system_v004.blend`: editable scene with 4K / 128-sample still settings.
- `optical_orbit_v004.blend`: orbit camera active, 192 frames at 24 fps.
- `orbit_v004.mp4`: 8-second, 360-degree Z-axis orbit at 1280x960, GPU Cycles.
- `overview_v004_4k.png`, `detail_v004.png`: still-image previews.

The scene already contains the orbit rig. In the animation file, press Numpad 0
for camera view and Space to play the timeline; select Material Preview for
responsive playback. This is a camera-orbit animation, not a physical light
propagation simulation. Voice-over has not been added.

Styling references: the user's supplied two optical-layout images, plus the
optical-mount vocabulary shown by [Edmund Optics](https://www.edmundoptics.com/knowledge-center/application-notes/optomechanics/how-to-set-up-an-optical-lab/).
No external image has been substituted for the editable Blender model.
