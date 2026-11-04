"""OpenToonz scenes (WP-34): a shot's drawn levels as an OpenToonz 1.8 scene (.tnz) that OpenToonz's own renderer,
tcomposer, renders.

What goes over is what OpenToonz is built for, frame-by-frame animation: each drawn level (template "level") becomes a
raster level, one PNG per drawing at its artboard size, saved at 120 dpi so a drawing pixel is a camera pixel when the
column is at 100%; the xsheet holds, per frame, which drawing is exposed (from the bake, so a clip's timing, speed
and loops come over exactly); the column's pegbar carries the character's position and scale as a key on every
frame (linear between keys: exact). The camera is 1080x1920 (9 x 16 inches at 120 dpi). Cut-out puppets are not
OpenToonz levels: they are listed as not exported. The scene's file format follows OpenToonz's own sample scenes
(opentoonz_sample, read for the format only).
"""
import base64
import io
from pathlib import Path

from PIL import Image

DPI = 120


def _img(st, root):
    src = st["image"]
    data = base64.b64decode(src.split(",", 1)[1]) if src.startswith("data:") else (Path(root) / src).read_bytes()
    return Image.open(io.BytesIO(data)).convert("RGBA")


def drawing_png(puppet, strokes, root):
    """one drawing (its image strokes) composited on the puppet's artboard"""
    aw, ah = puppet["artboard"]
    canvas = Image.new("RGBA", (int(aw), int(ah)), (0, 0, 0, 0))
    for st in strokes:
        if "image" not in st:
            continue
        im = _img(st, root).resize((max(1, round(st["w"])), max(1, round(st["h"]))), Image.LANCZOS)
        canvas.alpha_composite(im, (round(st["x"]), round(st["y"])))
    return canvas


def _ch(name, keys, default):
    """an animatable channel: a default and, if it moves, a linear key on each frame given"""
    if not keys or len({round(v, 5) for _, v in keys}) == 1:
        return f"<{name}><default>{(keys[0][1] if keys else default):.6g}</default></{name}>"
    return (f"<{name}><default>{default:.6g}</default><keyframes>"
            + "".join(f"<L>{f} {v:.6g}</L>" for f, v in keys) + f"</keyframes></{name}>")


def scene(size, n_frames, fps, levels, columns):
    """levels: [{id, name, path}] ; columns: [{level, cells: [drawing number or None per frame], x, y, sc, sx: [(frame, value)]}]
    -> the .tnz text"""
    W, H = size; cw, chh = W / DPI, H / DPI
    cam = f"<cameraSize>{cw:.6g} {chh:.6g}</cameraSize><cameraRes>{W} {H}</cameraRes><cameraXPrevalence>1</cameraXPrevalence><interestRect>0 0 -1 -1</interestRect>"
    out = [f'<tnz framecount="{n_frames}" version="71.1">', '<generator>"Doodleberry (OpenToonz 1.8 scene)"</generator>', "<properties>",
           f"<cameras><camera>{cam}</camera></cameras>",
           '<outputs><output name="main"><range>0 -1</range><step>1</step><shrink>1</shrink><applyShrinkToViewer>0</applyShrinkToViewer>'
           f'<fps>{fps}</fps><path>"+outputs/frame.png"</path><bpp>32</bpp><multimedia>0</multimedia><threadsIndex>2</threadsIndex>'
           '<maxTileSizeIndex>0</maxTileSizeIndex><subcameraPrev>0</subcameraPrev><stereoscopic>0 0.05</stereoscopic><resquality>0</resquality>'
           '<fieldprevalence>0</fieldprevalence><gamma>1</gamma><timestretch>25 25</timestretch></output></outputs>',
           "</properties>", "<levelSet><levels>"]
    for lv in levels:
        out.append(f"<level id='{lv['id']}'>{lv['name']}<info dpiType=\"image\"/><path>\"{lv['path']}\"</path></level>")
    out.append("</levels><folder name=\"Cast\" type=\"default\"><levels>" + "".join(f"<level id='{lv['id']}'/>" for lv in levels) + "</levels></folder></levelSet>")
    out.append("<xsheet><columns>")
    # id='n' is OpenToonz's object table: one numbering for the whole file (levels, columns, fxs), each id once
    nid = max([lv["id"] for lv in levels] or [0]); col_fx = []
    for ci, col in enumerate(columns):
        runs, f = [], 0
        cells = col["cells"]
        while f < len(cells):   # runs of frames exposing consecutive drawings: "row count level drawing increment"
            if cells[f] is None:
                f += 1; continue
            g = f
            while g + 1 < len(cells) and cells[g + 1] == cells[f]:
                g += 1
            runs.append(f"<cell>{f} {g - f + 1} <level id='{col['level']}'/>{cells[f]:04d} 0</cell>")
            f = g + 1
        col_id, fx_id = nid + 1, nid + 2; nid += 2; col_fx.append(fx_id)
        out.append(f"<levelColumn id='{col_id}'><status>0</status><cells>{''.join(runs)}</cells>"
                   f"<fx><Toonz_columnFx id='{fx_id}'><params></params><ports></ports><numberId>{ci}</numberId><name>Col{ci + 1}</name><fxId>\"\"</fxId><opened>0</opened></Toonz_columnFx></fx></levelColumn>")
    out.append("</columns><pegbars>")
    peg = lambda pid, parent, extra="": (f'<pegbar id="{pid}"><parent handle="B" id="{parent}" parentHandle="B"></parent><isOpened>0</isOpened>'
                                        f"<center>0 0 0 0</center><status>0</status>{extra}<nodePos>0 0</nodePos></pegbar>")
    out.append(f'<pegbar activeboth="yes" id="Camera1"><parent handle="B" id="None" parentHandle="B"></parent><isOpened>0</isOpened><center>0 0 0 0</center>'
               f"<status>0</status><nodePos>0 0</nodePos><camera>{cam}</camera></pegbar>")
    out.append(peg("Table", "None"))
    for ci, col in enumerate(columns):
        out.append(peg(f"Col{ci + 1}", "Table", _ch("x", col["x"], 0) + _ch("y", col["y"], 0) + _ch("sx", col["sx"], 1) + _ch("sc", col["sc"], 1)))
    out.append("<grid_dimension>1</grid_dimension></pegbars>")
    out.append("<fxnodes><terminal>" + "".join(f"<fxnode><Toonz_columnFx id='{i}'/></fxnode>" for i in col_fx) + "</terminal>"
               f"<xsheet><Toonz_xsheetFx id='{nid + 1}'><params></params><ports></ports><dagNodePos>0 0</dagNodePos><numberId>0</numberId><name>Xsheet</name><fxId>\"\"</fxId><opened>0</opened></Toonz_xsheetFx></xsheet>"
               f"<output><Toonz_outputFx id='{nid + 2}'><params></params><ports><source><Toonz_xsheetFx id='{nid + 1}'/></source></ports><dagNodePos>0 0</dagNodePos><numberId>0</numberId><name>Output</name><fxId>\"\"</fxId><opened>0</opened></Toonz_outputFx></output>"
               "<grid_dimension>1</grid_dimension></fxnodes></xsheet><history></history></tnz>")
    return "\n".join(out) + "\n"


def project(folder, name="doodleberry"):
    """make the export folder its own OpenToonz project (tcomposer and OpenToonz look for scenes.xml beside a scene and
    a <name>_otprj.xml in the project folder it names): scenes, drawings and inputs here, renders in render/"""
    folder = Path(folder)
    (folder / "scenes.xml").write_text('<parentProject type="projectFolder">"."</parentProject>\n')
    dirs = {"+scenes": ".", "+drawings": ".", "+inputs": ".", "+extras": ".", "+outputs": "render", "+palettes": "."}
    (folder / f"{name}_otprj.xml").write_text("<project><version>70 1</version><folders>"
                                              + "".join(f'<folder name="{k}" path="{v}"/>' for k, v in dirs.items()) + "</folders></project>\n")


def column_from_bake(cast_frames, puppet, size, drawing_index):
    """a level character's xsheet cells and pegbar keys from its baked frames"""
    W, H = size; aw, ah = puppet["artboard"]
    # the point the player puts at the character's (x, y): its hip's x and its ground line (as player.js and bake.mjs)
    hip = (puppet["parts"].get("hip") or {}).get("pivot") or [aw / 2, puppet.get("ground", ah)]
    piv = (hip[0], puppet.get("ground", ah))
    cells, x, y, sc, sx = [], [], [], [], []
    for f, fr in enumerate(cast_frames):
        d = fr.get("level"); cells.append(drawing_index.get(d) if d else None)
        s, flip = fr["s"], fr.get("flip", 1)
        # the drawing's centre (OpenToonz puts a level's image centre at its column's origin), from the ground point at (x, y)
        cxp = fr["x"] + (aw / 2 - piv[0]) * s * flip + fr.get("offset", [0, 0])[0] * s * flip
        cyp = fr["y"] + (ah / 2 - piv[1]) * s + fr.get("offset", [0, 0])[1] * s
        x.append((f, (cxp - W / 2) / DPI)); y.append((f, -(cyp - H / 2) / DPI)); sc.append((f, s)); sx.append((f, float(flip)))
    return {"cells": cells, "x": x, "y": y, "sc": sc, "sx": sx}
