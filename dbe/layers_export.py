"""Puppet to editable layers (plan 1.3, the other direction): hand a puppet to an artist as a layered file they can
repaint, then bring it back with `puppet.import`.

    python dbe/layers_export.py PUPPET.json OUT.(svg|ora|psd) [{"pivots": true}]

- SVG: one Inkscape layer per part, swap sets as a layer holding one sub-layer per shape (all but the first hidden),
  colours as plain hex with a `data-slot` attribute so the palette slots survive the round trip.
- ORA / PSD: the same layers rasterised with the SVG renderer (Chromium) at the artboard size. PSD needs psd-tools.
- `pivots: true` adds a `pivots` layer with a `pivot:<part>` dot per joint, so repainted parts keep exact joints.
"""
import io
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
INK = "http://www.inkscape.org/namespaces/inkscape"


def _col(v, pal):
    return pal.get(v, v) if v and v != "none" else "none"


def _strokes_svg(strokes, pal):
    out = []
    for st in strokes:
        if st.get("image"):
            out.append(f'<image href="{st["image"]}" x="{st["x"]}" y="{st["y"]}" width="{st["w"]}" height="{st["h"]}" preserveAspectRatio="none"'
                       + (f' opacity="{st["opacity"]}"' if st.get("opacity") is not None else "") + "/>")
            continue
        fill, line = _col(st.get("fill"), pal), _col(st.get("stroke"), pal)
        slot = st.get("fill") if st.get("fill") in pal else (st.get("stroke") if fill == "none" and st.get("stroke") in pal else None)
        a = [f'd="{st["d"]}"', f'fill="{fill}"']
        if line != "none":
            a += [f'stroke="{line}"', f'stroke-width="{st.get("width", 3)}"', 'stroke-linejoin="round"', 'stroke-linecap="round"']
        if st.get("opacity") is not None:
            a.append(f'opacity="{st["opacity"]}"')
        if slot:
            a.append(f'data-slot="{slot}"')
        out.append("<path " + " ".join(a) + "/>")
    return "".join(out)


def layers(puppet, pivots=False):
    """-> list of (name path, svg markup, hidden) in painter order, plus the artboard"""
    pal = puppet.get("palette", {})
    items = []
    for pid, part in puppet["parts"].items():
        if part.get("strokes"):
            items.append((part.get("z", 0), [pid], _strokes_svg(part["strokes"], pal), False))
    for sid, sw in (puppet.get("swaps") or {}).items():
        first = True
        for shp, strokes in sw.get("shapes", {}).items():
            if strokes:
                items.append((sw.get("z", 40), [sid, shp], _strokes_svg(strokes, pal), not first)); first = False
    items.sort(key=lambda t: t[0])
    out = [(names, svg, hid) for _, names, svg, hid in items]
    if pivots:
        for pid, part in puppet["parts"].items():
            x, y = part["pivot"]
            out.append((["pivots", f"pivot:{pid}"], f'<circle cx="{x}" cy="{y}" r="3" fill="#ff00aa"/>', True))
    return out


def to_svg(puppet, pivots=False):
    W, H = puppet["artboard"]
    body, open_group = [], None
    for names, svg, hid in layers(puppet, pivots):
        style = ' style="display:none"' if hid else ""
        if len(names) == 2:
            if open_group != names[0]:
                if open_group:
                    body.append("</g>")
                body.append(f'<g inkscape:groupmode="layer" inkscape:label="{escape(names[0])}">'); open_group = names[0]
            body.append(f'<g inkscape:groupmode="layer" inkscape:label="{escape(names[1])}"{style}>{svg}</g>')
        else:
            if open_group:
                body.append("</g>"); open_group = None
            body.append(f'<g inkscape:groupmode="layer" inkscape:label="{escape(names[0])}"{style}>{svg}</g>')
    if open_group:
        body.append("</g>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="{INK}" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<!-- {escape(puppet.get("name", ""))}: exported by Doodleberry for repainting; re-import with puppet.import -->'
            + "".join(body) + "</svg>")


def _rasterise(puppet, pivots):
    """render each layer to a full-artboard RGBA PNG with Chromium"""
    W, H = [int(round(v)) for v in puppet["artboard"]]
    L = layers(puppet, pivots)
    with tempfile.TemporaryDirectory() as td:
        spec = Path(td) / "spec.json"
        spec.write_text(json.dumps({"w": W, "h": H, "layers": [svg for _, svg, _ in L], "out": td}))
        js = r"""
const { createRequire } = require('module'); const fs = require('fs');
const { chromium } = require('playwright');
(async () => {
  const s = JSON.parse(fs.readFileSync(process.argv[1], 'utf8'));
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: s.w, height: s.h } });
  await p.setContent('<html><body style="margin:0;background:transparent"><svg id="s" xmlns="http://www.w3.org/2000/svg" width="' + s.w + '" height="' + s.h + '"></svg></body></html>');
  for (let i = 0; i < s.layers.length; i++) {
    await p.evaluate(m => { document.getElementById('s').innerHTML = m; }, s.layers[i]);
    await p.screenshot({ path: s.out + '/' + i + '.png', omitBackground: true });
  }
  await b.close();
})();
"""
        r = subprocess.run(["node", "-e", js, str(spec)], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(r.stderr[-800:])
        from PIL import Image
        return W, H, [(names, Image.open(Path(td) / f"{i}.png").convert("RGBA"), hid) for i, (names, _, hid) in enumerate(L)]


def to_ora(puppet, out, pivots=False):
    W, H, L = _rasterise(puppet, pivots)
    z = zipfile.ZipFile(out, "w")
    z.writestr("mimetype", "image/openraster", compress_type=zipfile.ZIP_STORED)
    groups, xml, n = {}, [], 0
    for names, im, hid in reversed(L):  # stack.xml lists the top layer first
        bb = im.getchannel("A").getbbox()
        if not bb:
            continue
        buf = io.BytesIO(); im.crop(bb).save(buf, "PNG"); src = f"data/{n}.png"; n += 1
        z.writestr(src, buf.getvalue())
        tag = f'<layer name="{escape(names[-1])}" src="{src}" x="{bb[0]}" y="{bb[1]}" visibility="{"hidden" if hid else "visible"}"/>'
        if len(names) == 2:
            if names[0] not in groups:
                groups[names[0]] = []; xml.append(("group", names[0]))
            groups[names[0]].append(tag)
        else:
            xml.append(("layer", tag))
    body = "".join(f'<stack name="{escape(v)}">' + "".join(groups[v]) + "</stack>" if k == "group" else v for k, v in xml)
    z.writestr("stack.xml", f'<?xml version="1.0" encoding="UTF-8"?><image version="0.0.3" w="{W}" h="{H}"><stack>{body}</stack></image>')
    from PIL import Image
    comp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for names, im, hid in L:
        if not hid:
            comp.alpha_composite(im)
    buf = io.BytesIO(); comp.save(buf, "PNG"); z.writestr("mergedimage.png", buf.getvalue())
    th = comp.copy(); th.thumbnail((256, 256)); buf = io.BytesIO(); th.save(buf, "PNG"); z.writestr("Thumbnails/thumbnail.png", buf.getvalue())
    z.close()


def to_psd(puppet, out, pivots=False):
    from psd_tools import PSDImage
    W, H, L = _rasterise(puppet, pivots)
    psd = PSDImage.new("RGBA", (W, H))
    from psd_tools.api.layers import PixelLayer
    groups = {}
    for names, im, hid in L:  # bottom first
        bb = im.getchannel("A").getbbox()
        if not bb:
            continue
        if len(names) == 2:
            if names[0] not in groups:
                groups[names[0]] = psd.create_group(name=names[0])
            lay = PixelLayer.frompil(im.crop(bb), groups[names[0]], names[1], bb[1], bb[0])
        else:
            lay = PixelLayer.frompil(im.crop(bb), psd, names[0], bb[1], bb[0])
        lay.visible = not hid
    psd.save(out)


if __name__ == "__main__":
    pz = json.loads(Path(sys.argv[1]).read_text()); out = sys.argv[2]
    opts = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    ext = Path(out).suffix.lower()
    if ext == ".svg":
        Path(out).write_text(to_svg(pz, opts.get("pivots", False)))
    elif ext == ".ora":
        to_ora(pz, out, opts.get("pivots", False))
    elif ext == ".psd":
        to_psd(pz, out, opts.get("pivots", False))
    else:
        raise SystemExit("output must be .svg, .ora or .psd")
    print(json.dumps({"out": out}))
