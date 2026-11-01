# 2D animation tools in this container (tested 2026-11-01, Ubuntu 24.04, 4 CPU, no GPU)

| tool | installed how | programmatic interface | headless render | measured | verdict |
|------|---------------|------------------------|-----------------|----------|---------|
| **Synfig 1.5.1** | `apt install synfig` (CLI) | write `.sif` XML: layers (region, outline, circle, gradients), animated waypoints, groups, **Skeleton/bones deformation**, switch layers for mouth swaps, Papagayo lip-sync import | `synfig file.sif -t png -o seq.png` (also ffmpeg targets) | 49 frames at 540×960 in 0.7 s (`tools/synfig/blob_test.sif`) | **works**, very fast; good backend for vector cut-out puppets generated from code |
| **Blender 5.2.3 Grease Pencil v3** | already installed (tarball) | full Python API: layers, frames, drawings, strokes (positions, radius, cyclic, materials with fill/stroke), modifiers (noise, thickness, line art from 3D), armature rigging of GP objects, cameras, lights | `blender -b --gpu-backend vulkan --python …` (EEVEE via software Vulkan) | 2.4 s/frame at 540×960 (`tools/blender/grease_pencil_test.py`) | **works**; richest look (brush strokes, 2D in 3D space, line art) but slowest |
| **Pencil2D 0.6.6** | `apt install pencil2d` + `xvfb` | none (no scripting); authoring means writing its `.pclx` zip (main.xml + data) by hand | `xvfb-run pencil2d in.pclx -o out.mp4` | CLI export runs (1 s), but my hand-written `.pclx` exported blank frames | renders existing files only; it's a hand-drawing tool, not a pipeline backend |
| **OpenToonz** | not in Ubuntu apt; GitHub release pages unreachable from here; Linux needs Flatpak or a source build | QtScript console inside the GUI; `tcomposer` renders existing scenes; scenes are `.tnz` XML | needs a build plus Xvfb | not installed | possible but heavy; weakest programmatic surface for generating content |

Notes: Synfig's canvas `bgcolor` isn't drawn (add a background layer); the Grease Pencil test showed the stroke but not the fill
(GP v3 fill needs the material's fill settings checked) and draws over a grey film, not the world colour. Both are fixable details.
