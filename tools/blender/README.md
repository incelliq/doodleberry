# Headless Blender tools (tested with Blender 5.2.3 LTS, Linux x64, no GPU)

| script | what it does |
|--------|--------------|
| `list_actions.py` | imports glTF characters and prints their animation clips |
| `render_test.py -- CYCLES\|BLENDER_EEVEE` | poses a character mid-animation on a lit stage and renders one 1080×1920 frame |
| `mpfb_human.py` | generates a MakeHuman body with MPFB2, adds the 53-bone `game_engine` rig, exports glTF |

```bash
B=/path/to/blender-5.2.3-linux-x64/blender
ASSETS=/path/to/assets OUT=out/ $B -b --factory-startup --python list_actions.py
# EEVEE without a GPU: software Vulkan (apt: mesa-vulkan-drivers libegl1 libegl-mesa0 libgl1-mesa-dri libgbm1)
ASSETS=... OUT=out/ $B -b --factory-startup --gpu-backend vulkan --python render_test.py -- BLENDER_EEVEE
# MPFB2: blender -b --command extension install-file -r user_default -e add-on-mpfb-v2.0.18.zip
OUT=out/ $B -b --python mpfb_human.py
```

See `../../references/3d-pipeline-research.md` for timings, asset licences and the recommended setup.
