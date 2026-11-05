"""Editor hand-off (WP-22): a film as a package an editor opens in their own tool, with the shots, the stems and the
captions in place, and with the cut written in every interchange format we can verify:

    build/handoff/
      media/<shot>.mp4          the shots as rendered (no burned captions)
      audio/voice.wav, music.wav, sfx.wav   the stems at their mixed level (24-bit)
      captions.srt, captions.vtt
      timeline.otio             OpenTimelineIO (the source of the others)
      timeline.kdenlive         Kdenlive (KDE's OTIO adapter, for Kdenlive before 25.04; later versions open
                                timeline.otio natively)
      timeline.mlt              MLT XML for melt
      timeline.xml              Final Cut Pro 7 XML (DaVinci Resolve, Premiere)
      timeline.fcpxml           Final Cut Pro X
      timeline.edl              CMX 3600 (picture)
      camera/<shot>.chan, .csv  each shot's camera per frame, for compositors
      README.txt

Captions travel as an SRT next to the timeline and as markers in it; the OTIO adapters write the other formats, and
the package records which reference tools read them back (OTIO, melt, Kdenlive when installed).
"""
import json
import math
import shutil
import subprocess
from pathlib import Path

from . import ROOT

# MLT's player: `melt` (Debian), `melt-7` or `mlt-melt` (Fedora's mlt 7)
MELT = shutil.which("melt") or shutil.which("melt-7") or shutil.which("mlt-melt")


def _frames(mp4):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(mp4)],
                       capture_output=True, text=True)
    return int(r.stdout.strip() or 0)


def _srt(path):
    """[(start s, end s, text)] from an SRT file"""
    out, block = [], []
    for line in list(Path(path).read_text(encoding="utf-8").splitlines()) + [""]:
        if line.strip():
            block.append(line); continue
        if len(block) >= 3 and "-->" in block[1]:
            a, b = [x.strip().replace(",", ".") for x in block[1].split("-->")]
            sec = lambda s: sum(float(p) * m for p, m in zip(s.split(":"), (3600, 60, 1)))
            out.append((sec(a), sec(b), " ".join(block[2:])))
        block = []
    return out


def timeline(name, title, fps, shots, stems, captions):
    """the OTIO timeline: V1 the shots in order, A1-A3 the stems, the captions as markers"""
    import opentimelineio as otio
    RT, TR = otio.opentime.RationalTime, otio.opentime.TimeRange
    tl = otio.schema.Timeline(name=title, global_start_time=RT(0, fps))
    tl.metadata["doodleberry"] = {"film": name, "fps": fps}
    v = otio.schema.Track(name="V1", kind=otio.schema.TrackKind.Video)
    for sid, path, n in shots:
        ref = otio.schema.ExternalReference(target_url=path, available_range=TR(RT(0, fps), RT(n, fps)))
        v.append(otio.schema.Clip(name=sid, media_reference=ref, source_range=TR(RT(0, fps), RT(n, fps))))
    tl.tracks.append(v)
    total = sum(n for _, _, n in shots)
    for i, (stem, path) in enumerate(stems):
        a = otio.schema.Track(name=f"A{i + 1} {stem}", kind=otio.schema.TrackKind.Audio)
        ref = otio.schema.ExternalReference(target_url=path, available_range=TR(RT(0, fps), RT(total, fps)))
        a.append(otio.schema.Clip(name=stem, media_reference=ref, source_range=TR(RT(0, fps), RT(total, fps))))
        tl.tracks.append(a)
    for (a, b, text) in captions:
        m = otio.schema.Marker(name=text, marked_range=TR(RT(round(a * fps), fps), RT(max(1, round((b - a) * fps)), fps)), color=otio.schema.MarkerColor.YELLOW)
        m.metadata["doodleberry"] = {"kind": "caption"}
        v.markers.append(m)
    return tl


def fix_profile(path, W, H, fps):
    """the adapters write a fixed 1920x1080 profile (Kdenlive) or none (MLT): set the film's own size and rate"""
    import xml.etree.ElementTree as ET
    from math import gcd
    t = ET.parse(path); root = t.getroot(); pr = root.find("profile")
    if pr is None:
        pr = ET.Element("profile"); root.insert(0, pr)
    for k in list(pr.attrib):
        pr.attrib.pop(k)
    g = gcd(W, H)
    pr.attrib.update({"description": f"{W}x{H} {fps} fps (Doodleberry)", "width": str(W), "height": str(H), "frame_rate_num": str(fps), "frame_rate_den": "1",
                      "display_aspect_num": str(W // g), "display_aspect_den": str(H // g), "sample_aspect_num": "1", "sample_aspect_den": "1",
                      "progressive": "1", "colorspace": "709"})
    # MLT reads "133.0" as seconds, not frames: the MLT adapter writes frames as floats, so make them whole numbers
    import re as _re
    for el in root.iter():
        for k in ("in", "out", "length"):
            v = el.attrib.get(k)
            if v and _re.fullmatch(r"-?\d+\.0", v):
                el.attrib[k] = v[:-2]
        if el.tag == "property" and el.attrib.get("name") in ("length", "in", "out") and el.text and _re.fullmatch(r"-?\d+\.0", el.text.strip()):
            el.text = el.text.strip()[:-2]
    t.write(path, encoding="utf-8", xml_declaration=True)


def write_all(tl, out, size=None, fps=None):
    """every interchange format; returns {format: file or error}"""
    import copy
    import opentimelineio as otio
    res = {}
    otio.adapters.write_to_file(tl, str(out / "timeline.otio"))
    res["otio"] = "timeline.otio"
    for fmt, fn, adapter in (("kdenlive", "timeline.kdenlive", "kdenlive"), ("mlt", "timeline.mlt", "mlt_xml"), ("fcp7_xml", "timeline.xml", "fcp_xml"),
                             ("fcpxml", "timeline.fcpxml", "fcpx_xml"), ("edl", "timeline.edl", "cmx_3600")):
        t = copy.deepcopy(tl)
        if fmt == "edl":   # CMX 3600 carries one picture track
            t.tracks[:] = [x for x in t.tracks if x.kind == otio.schema.TrackKind.Video][:1]
        try:
            otio.adapters.write_to_file(t, str(out / fn), adapter_name=adapter)
            if fmt in ("kdenlive", "mlt") and size:
                fix_profile(out / fn, size[0], size[1], fps)
            res[fmt] = fn
        except Exception as e:   # an adapter that cannot express something says so
            res[fmt] = f"error: {str(e)[:200]}"
    return res


def read_back(out, fps=30):
    """read each written file with OTIO again (a format we wrote must come back with the same clips)"""
    import opentimelineio as otio
    got = {}
    for fn, adapter in (("timeline.otio", None), ("timeline.kdenlive", "kdenlive"), ("timeline.xml", "fcp_xml"), ("timeline.fcpxml", "fcpx_xml"), ("timeline.edl", "cmx_3600")):
        p = out / fn
        if not p.exists():
            continue
        try:
            kw = {"rate": fps} if adapter == "cmx_3600" else {}   # an EDL carries timecode, not its rate
            t = otio.adapters.read_from_file(str(p), adapter_name=adapter, **kw) if adapter else otio.adapters.read_from_file(str(p))
            vt = [x for x in t.tracks if x.kind == otio.schema.TrackKind.Video]
            got[fn] = {"video_clips": [c.name for c in vt[0].find_clips()] if vt else [], "audio_tracks": sum(1 for x in t.tracks if x.kind == otio.schema.TrackKind.Audio),
                       "duration_frames": int(round(t.duration().to_frames()))}
        except Exception as e:
            got[fn] = {"error": str(e)[:200]}
    return got


def chan(camera_frames, W, H, out_base):
    """a shot's camera per frame as a Nuke .chan (frame tx ty tz rx ry rz focal) and a CSV of the 2D camera: the same
    perspective camera the 3D sets use (1 px = 1 cm on the stage plane, the camera 12 m in front, dolly for zoom)"""
    K, D0 = 0.01, 12.0
    lens = 18 * D0 / (W * K / 2)
    rows, csv = [], ["frame,cx,cy,zoom"]
    for f, (cx, cy, z) in enumerate(camera_frames):
        rows.append(f"{f + 1} {(cx - W / 2) * K:.5f} {-(cy - H / 2) * K:.5f} {D0 / z:.5f} 0 0 0 {lens:.4f}")
        csv.append(f"{f + 1},{cx:.3f},{cy:.3f},{z:.5f}")
    Path(str(out_base) + ".chan").write_text("\n".join(rows) + "\n")
    Path(str(out_base) + ".csv").write_text("\n".join(csv) + "\n")


def _y4m_frames(proc, W, H):
    """frames (bytes) from a yuv4mpegpipe stream, one at a time"""
    fs = W * H * 3 // 2
    head = proc.stdout.readline()
    if not head.startswith(b"YUV4MPEG2"):
        return
    while True:
        tag = proc.stdout.readline()
        if not tag.startswith(b"FRAME"):
            return
        buf = proc.stdout.read(fs)
        if len(buf) < fs:
            return
        yield buf


def melt_round_trip(out, fps, W, H, shots):
    """render the MLT project with melt and compare every frame with the shots it was built from, as decoded YUV 4:2:0
    (melt keeps the decoder's 4:2:0 picture: no rescale, no range or colour conversion), so an editor's render of the
    cut can be checked against ours byte for byte"""
    import numpy as np
    total = sum(n for _, _, n in shots)
    lst = out / "melt_concat.txt"
    lst.write_text("".join(f"file '{(out / p).resolve()}'\n" for _, p, _ in shots))
    m = subprocess.Popen([MELT or "melt", str(out / "timeline.mlt"), "in=0", f"out={total - 1}", "-consumer", "avformat:pipe:1", "f=yuv4mpegpipe", "vcodec=rawvideo",
                          "pix_fmt=yuv420p", "mlt_image_format=yuv420p", "rescale=none", "progressive=1", "color_range=mpeg", "an=1", "real_time=0", "terminate_on_pause=1"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, cwd=str(out))
    o = subprocess.Popen(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-f", "yuv4mpegpipe", "-pix_fmt", "yuv420p", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    n = same = 0; worst = 0
    for a, b in zip(_y4m_frames(m, W, H), _y4m_frames(o, W, H)):
        n += 1
        if a == b:
            same += 1
        else:
            worst = max(worst, int(np.abs(np.frombuffer(a, np.uint8).astype(int) - np.frombuffer(b, np.uint8).astype(int)).max()))
    for p in (m, o):
        p.stdout.close(); p.wait()
    lst.unlink()
    return {"melt_ok": m.returncode == 0 and n > 0, "frames": n, "expected": total, "identical": same, "max_diff": worst}


def self_test(tmp):
    """two generated shots and a stem: every format reads back with both clips, and melt renders the cut byte for byte"""
    tmp = Path(tmp); shutil.rmtree(tmp, ignore_errors=True)
    for sub in ("media", "audio"):
        (tmp / sub).mkdir(parents=True)
    W, H, fps = 720, 1280, 30   # HD: MLT reads untagged video under 720 lines as BT.601, and our films are HD (BT.709)
    for i, (src, n) in enumerate((("testsrc2", 20), ("testsrc", 15))):   # untagged, like our renders (smptebars tags itself BT.601)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"{src}=size={W}x{H}:rate={fps}", "-frames:v", str(n), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(tmp / "media" / f"s{i + 1}.mp4")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1.2", "-ar", "48000", str(tmp / "audio" / "voice.wav")], check=True)
    shots = [("s1", "media/s1.mp4", 20), ("s2", "media/s2.mp4", 15)]
    tl = timeline("test", "Hand-off test", fps, shots, [("voice", "audio/voice.wav")], [(0.1, 0.6, "Hello there")])
    written = write_all(tl, tmp, [W, H], fps)
    back = read_back(tmp, fps)
    rt = melt_round_trip(tmp, fps, W, H, shots)
    bad = []
    for fn, r in back.items():
        if r.get("video_clips") != ["s1", "s2"] or r.get("duration_frames") != 35:
            bad.append({fn: r})
    if [k for k, v in written.items() if str(v).startswith("error")]:
        bad.append({"written": written})
    if not (rt["melt_ok"] and rt["frames"] == 35 and rt["identical"] == 35):
        bad.append({"melt": rt})
    return bad, {"formats": sorted(back), "melt": rt}
