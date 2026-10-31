# 3D pipeline research: CC0 rigged characters and Claude-driven Blender (2026-10-31)

Goal: original 3D "what happens if…" fact shorts, rendered in this cloud container (4 CPU cores, 15 GB RAM,
no GPU, ~27 GB free disk), driven by Claude. Everything marked **tested** was run here.

## 1. Rigged characters with idle / walk / fall animations

| source | licence | what you get | idle | walk | fall / death | status here |
|--------|---------|--------------|------|------|--------------|-------------|
| **KayKit Character Pack: Adventurers** (Kay Lousberg) | CC0 (LICENSE.txt in repo) | 5 stylised chibi characters as GLB; 76 clips embedded per character | `Idle`, `Unarmed_Idle`, `2H_Melee_Idle` | `Walking_A/B/C`, `Walking_Backwards`, running, strafes | `Death_A`, `Death_B` (+ `_Pose` holds), `Hit_A/B`, `Lie_Down/Idle/StandUp`, `Sit_*`, jumps | **tested**: cloned from GitHub (142 MB), imported, listed, posed mid-fall, rendered |
| KayKit Character Animations | CC0 | 133 humanoid clips per rig size (Rig_Medium, Rig_Large); retargetable | yes | yes | deaths, hits | not downloaded (itch.io) |
| **Quaternius Universal Animation Library** (1 and 2) | CC0 | 120+ clips (UAL1) on a universal humanoid rig (UE/Godot/Unity compatible): 8-way locomotion, crawl, climb, sit, swim, hits, deaths; UAL2 adds parkour, talking, lying down, carrying, zombies | yes | yes | deaths (no clip literally named "fall" confirmed) | not downloaded (itch.io / Patreon, no direct links) |
| **Quaternius Universal Base Characters** | CC0 (a newer "QAL" licence is reported for future packs; this one still lists CC0) | 6 humanoid characters (superhero, regular, teen; male/female), ~13k tris, 20 hairstyles, eye/skin shaders, same humanoid rig as UAL | via UAL | via UAL | via UAL | not downloaded; **the best stylised-human pair with UAL** |
| RobotExpressive (Tomás Laulhé, mods Don McCurdy) | CC0 | robot with idle, walk, run, jump, death, wave, emotes + 3 face morphs | yes | yes | `Death` | **tested**: fetched via jsDelivr from the three.js repo |
| Gobkit Free Character Pack Vol.1 / Gobkit freebies | CC0 | low-poly GLBs, shared skeleton, clips Idle/Walk/Run/Death/Hit/Attack | yes | yes | `Death` | not downloaded |
| Kenney Animated Characters 1–3, Protagonists, Retro | CC0 | small rigged characters with a handful of clips (AC3: 4 skins, 3 animations) | yes | yes | not listed | not downloaded |
| **MakeHuman via MPFB2** (Blender extension) | code GPLv3; generated characters and bundled assets CC0 | realistic adult bodies (age, build, gender, ethnicity sliders), auto-rig (default, game_engine, Rigify), clothes/skin/hair from CC0 asset packs | via retarget | via retarget | via retarget | **tested**: extension installed headless, body generated (19,158 verts), `game_engine` rig (53 bones), exported GLB, rendered. Skin, eyes, hair and clothes need the separate MakeHuman system asset pack |
| Mixamo (Adobe) | **not CC0**: free with an Adobe account, commercial use allowed, but no redistribution of raw files and no ML training | huge clip library incl. falls, trips, knockdowns | yes | yes | many | not used (account + terms) |
| CMU Graphics Lab Motion Capture | free for research and commercial use (per CMU's page, as reported) | 2,605 BVH/AMC sequences | yes | yes | not confirmed | not downloaded |

Takeaways:
- **For realistic humans** (closest to the genre): MPFB2 bodies + CC0 clothes/hair, animated by retargeting UAL/KayKit clips or CMU mocap onto the MPFB rig. Rigify or a retarget script does the mapping.
- **For stylised humans quickly:** Quaternius Universal Base Characters + UAL (same rig, no retarget), or KayKit (works today, chibi style).
- **Falls:** use death clips (`Death_A/B`) and hit reactions, or blend `Hit` → `Death` → `Lie_Idle`; or hand-key/physics a fall in Blender (rigid-body ragdoll is possible but fiddly).

## 2. Claude-driven Blender: the options

| setup | how Claude drives it | runs headless here? | notes |
|-------|----------------------|---------------------|-------|
| **Claude Code + headless Blender scripts** | Claude writes bpy scripts, runs `blender -b --python`, inspects renders (as we do with the 2D engine) | **yes, tested** | no GUI, no MCP needed; fully reproducible and committable; the path for this repo |
| Blender Lab official MCP server + add-on (Blender Foundation) | MCP client → server → add-on executes Python in a running Blender | needs a running Blender session (GUI); headless not documented | requires Blender 5.1+, add-on v1.0.3; experimental; the page warns it executes LLM-generated code with no guards (use a VM) |
| Anthropic's Blender connector ("Claude for Creative Work", 28 Apr 2026) | Claude desktop/web connector built on the official server | desktop, with Blender open | best for interactive work on your own machine: scene analysis, batch edits, new UI tools |
| MCP for Blender (ahujasid, formerly "blender-mcp") | add-on opens a socket (localhost:9876); MCP server relays tool calls | GUI session | community project, popular, not official |
| Headless MCP forks (e.g. sandraschi/blender-mcp) | MCP tools spawn `blender --background` | yes (third-party) | maturity varies; no viewport screenshots in background mode |
| `bpy` from pip | `import bpy` in Python | yes | wheels track Blender's Python (3.11); our venv is 3.13, so the standalone tarball is simpler |
| Remote Control: your own computer | this cloud session attaches a folder on your machine | n/a | lets Claude run Blender on your GPU (seconds per frame instead of 6–14 s) |

## 3. Measured here (Blender 5.2.3 LTS, KayKit Knight posed mid-`Death_A`, lit stage, 1080×1920)

| engine | settings | per frame (steady state) | 45 s short (1,350 frames) |
|--------|----------|--------------------------|---------------------------|
| EEVEE | software Vulkan (`--gpu-backend vulkan`, Mesa lavapipe), full res | 13.8 s (first frame 23 s with shader compile) | ~5.2 h |
| EEVEE | same, 50 % res (540×960, upscale after) | 6.1 s | ~2.3 h |
| Cycles | CPU, 16 samples + denoise, 50 % res | 5.0 s | ~1.9 h |
| Cycles | CPU, 32 samples + denoise, full res | ~40 s (single frame) | ~15 h |
| EEVEE | OpenGL/EGL (Mesa) | works with EGL errors logged; 40 s first frame | slower than Vulkan |
| three.js (WebGL2, SwiftShader in headless Chromium) | soft shadows, full res | 1.6 s, 1 page | ~10 min with 4 workers |

Setup notes: EEVEE needs `libEGL.so.1` even in background mode (apt: `libegl1 libegl-mesa0 libgl1-mesa-dri libgbm1 mesa-vulkan-drivers`).
Cycles needs nothing extra. The Blender tarball is 1.2 GB unpacked.

## 3b. Packs now in hand (uploaded 2026-10-31), all CC0 per their licence files

| pack | contents | clips | used in |
|------|----------|-------|---------|
| Gobkit Free Character Pack Vol.1 | 8 everyday people (office lady, schoolkid, cashier, food courier, grandma shopper, stock clerk, store manager, shoplifter); 1 m tall, 1.8–3.4k tris, one shared 13-bone skeleton | Idle, Walk, Run, Death, Hit, Attack, Special (wave/jump/cheer) | `tools/three/cast-test.html` |
| Kenney Animated Characters Survivors 1.1 | one FBX character, 4 skins (2 survivors, 2 zombies) | idle, run, jump (separate FBX) | converted to GLB per skin |
| Quaternius Universal Animation Library [Standard] | UE-style 65-bone mannequin (fingers), 8.5k-vertex mannequin mesh; GLB/FBX, with and without root motion | 43 clips: Idle, Idle_Talking, Walk, Walk_Formal, Jog, Sprint, Crouch, Roll, Jump, Hit_Chest, Hit_Head, Death01, Sitting (enter/idle/talk/exit), Fixing_Kneeling, PickUp, Interact, Push, Driving, Swim, Dance, pistol, punch, sword, spell | walk → hit → death fall in the test |

Missing: Quaternius Universal Base Characters (same rig as UAL, so its 6 humans would play all 43 clips with no retargeting).


## 3c. CMU mocap and Innerscene (checked 2026-10-31)

**CMU Graphics Lab Motion Capture Database** (mocap.cs.cmu.edu): 2,605 trials, ASF/AMC + C3D, 120 fps. Terms on the
home page: "free for all uses"; "You may include this data in commercially-sold products, but you may not resell this
data directly, even in converted form"; please don't crawl (download individual trials, or the published zip).
Fall-type trials found by search: 90_16 fall on face, 90_17 BananaPeelSlip, 90_18 RugPullFall, 85_15 twist fall,
104_13 StumbleWalk, 22_12 / 23_12 A stumbles into B, 91_9 / 105_9 DrunkWalk, 77_19–24 limping, 91_16 / 105_16 Limp,
139_16–18 and 140_x get up from the ground, 13_x sit on a stool and stand up.
**Tested:** `tools/blender/cmu_retarget.py` retargets ASF/AMC straight onto the UAL mannequin (world-rotation
transfer with per-bone rest-direction alignment, root height scaled, 120→30 fps) and exports a GLB holding UAL's 43
clips plus the CMU ones. 90_16/17/18 retargeted in 13 s and play correctly in three.js (`tools/three/falls-test.html`).

**Innerscene Free 3D Parts Library** (innerscene.com/tools/library/3d-parts): 4,918 parts, mostly GLB; CC0 by its
library terms. Contributions come from viewer users (who must affirm they hold the rights) plus public-domain
collections, and each part page names its source. The People & figures tag has 360 items; the ones we checked
("Built by Innerscene from MakeHuman/MPFB CC0 body and skin assets") are dressed, textured, real-scale people
(~47k triangles) in fixed poses: lying flat, reclined or sitting up in bed, seated, standing groups, queues,
audiences. They are **static meshes with no armature**, so they suit set dressing (a hospital ward, a waiting room,
a crowd) rather than animated actors. Direct download endpoint: `/api/library/<slug>/download`.
Check each part's source line before use; prefer items marked as Innerscene/MakeHuman-derived.


## 3d. Universal Base Characters [Standard] (downloaded 2026-10-31) and Quaternius animal packs

**UBC Standard** (CC0, `License_Standard.txt`): the free tier holds 2 full bodies (Superhero_Male, Superhero_Female; glTF
for Godot/UE and FBX for Unity) with dark/light skin textures, normal and roughness maps, eye textures, plus 8 hair and
eyebrow meshes (buzzed, buzzed female, long, buns, simple parted, beard, two eyebrow sets) both "origin at 0" and
"rigged to head bone". Bone names match the UAL skeleton exactly (pelvis, spine_01…, hand_l, Head…), so every UAL clip
and every CMU clip retargeted by `cmu_retarget.py` plays on them by name, hair included (each hair glTF carries the
same skeleton; play the same clip on it). **Tested:** `tools/three/ubc-slip-test.html`, a man walks into a kitchen,
slips on a banana peel (CMU 90_17) and falls while a woman talks and flinches (UAL clips); 240 frames in 135 s.
The paid Source tier adds the other 4 bodies (regular and teen proportions).

**Quaternius Ultimate Animated Animals (July 2021), Farm Animals, Ultimate Nature Pack (June 2019)** were shared as
public Google Drive folders. Listing works (`embeddedfolderview`); file downloads returned Google's
"Quota exceeded: too many users have viewed or downloaded this file recently" page, so nothing was fetched.
Contents seen: Animated Animals glTF/FBX/blend for Alpaca, Bull, Cow, Deer, Donkey, Fox, Horse, Horse_White, Husky,
ShibaInu, Stag, Wolf; Farm Animals FBX/OBJ/blend for Cow, Horse, Llama, Pig, Pug, Sheep, Zebra; Nature Pack blends,
FBX and OBJ. Fix: download each folder as a zip in a browser and upload it.

## 4. Recommendation

1. **Blender headless as the asset factory, driven by Claude Code:** generate MPFB humans (or load Quaternius/KayKit), dress them,
   retarget UAL/KayKit/CMU clips, bake animation, author sets, export GLB. All scripted, committed, reproducible.
2. **Final render, two tiers:**
   - fast tier: three.js in our existing renderer (same voice/caption/audio/QA pipeline), minutes per short;
   - quality tier: Blender EEVEE at 540×960 then 2× upscale (~2 h per 45 s here), or EEVEE on your GPU via Remote Control (minutes).
3. **Interactive art direction** on your desktop through Anthropic's Blender connector, if you want to pose and light by conversation.
4. **Skip for now:** ML auto-riggers (UniRig: MIT code, but checkpoints carry their own terms and it wants an 8 GB CUDA GPU) and
   text-to-motion models (NVIDIA Kimodo: Apache code, weights under NVIDIA licences; HY-Motion, MotionGPT, MDM licences unverified).
   They need a GPU and licence review.

## Sources
- KayKit Adventurers (CC0): https://kaylousberg.itch.io/kaykit-adventurers · animations: https://kaylousberg.itch.io/kaykit-character-animations
- Quaternius UAL: https://quaternius.com/packs/universalanimationlibrary.html · Base Characters: https://quaternius.com/packs/universalbasecharacters.html
- Gobkit: https://gobkit.itch.io/gobkit-free-character-pack-vol-1 · Kenney: https://kenney.nl/assets/animated-characters-2
- MPFB 2 (CG Channel): https://www.cgchannel.com/2025/03/check-out-open-source-blender-character-generation-plugin-mpfb-2 · extension: https://extensions.blender.org/add-ons/mpfb/
- Mixamo licensing FAQ: https://community.adobe.com/t5/mixamo-discussions/mixamo-faq-licensing-royalties-ownership-eula-and-tos/td-p/13234775
- CMU mocap: https://cgpress.org/archives/carnegie-mellon-university-motion-capture-database.html
- Blender Lab MCP server: https://www.blender.org/lab/mcp-server/ · comparison: https://www.strayspark.studio/blog/official-blender-mcp-server-comparison-2026
- Claude for Creative Work: https://www.unite.ai/anthropic-wires-claude-into-photoshop-blender-and-ableton/
- MCP for Blender: https://github.com/ahujasid/mcp-for-blender · headless fork: https://github.com/sandraschi/blender-mcp
- Blender as a Python module: https://docs.blender.org/api/current/info_advanced_blender_as_bpy.html
- UniRig: https://github.com/VAST-AI-Research/UniRig · Kimodo: https://rits.shanghai.nyu.edu/ai/nvidia-releases-kimodo-controllable-text-to-motion-for-characters-and-humanoid-robots/
