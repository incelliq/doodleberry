"""Pose detectors compared by measured accuracy (WP-12): MediaPipe Pose Landmarker (what act-out uses), RTMPose via
rtmlib, and Ultralytics YOLO11-pose, on single-person photos from COCO val2017 with their annotated keypoints.

Score: COCO's Object Keypoint Similarity (OKS, its per-keypoint sigmas, over the annotated keypoints, the person's
area as scale) per image, the share of images with OKS >= 0.5 and >= 0.75 (as COCO's AP thresholds, here per image:
one person each), the mean OKS, and the CPU time per image. MediaPipe's 33 landmarks map onto COCO's 17.
Sapiens (Meta, 0.3B, CC BY-NC 4.0) runs top-down on the same YOLOX person boxes rtmlib gives RTMPose. OpenPose runs
bottom-up (part affinity fields) as CMU's body model in the PyTorch port vendored in vendor/openpose.
"""
import json
import time
from pathlib import Path

import numpy as np

SIGMAS = np.array([.26, .25, .25, .35, .35, .79, .79, .72, .72, .62, .62, 1.07, 1.07, .87, .87, .89, .89]) / 10.0
MP_TO_COCO = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]   # nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles


def oks(pred, gt, area):
    """pred: (17, 2); gt: COCO [x, y, v] * 17"""
    g = np.array(gt, float).reshape(17, 3); vis = g[:, 2] > 0
    if not vis.any() or pred is None:
        return 0.0
    d2 = ((pred[:, :2] - g[:, :2]) ** 2).sum(1)
    e = d2 / (2 * (SIGMAS ** 2) * (area + np.spacing(1)) * 4)   # COCO: s^2 = area, k = 2 sigma
    return float(np.exp(-e)[vis].mean())


def mediapipe_detector(model_path):
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    lm = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(model_path)), num_poses=1))
    def run(img):
        h, w = img.shape[:2]
        r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(img)))
        if not r.pose_landmarks:
            return None
        p = r.pose_landmarks[0]
        return np.array([[p[i].x * w, p[i].y * h] for i in MP_TO_COCO])
    return run


def rtmlib_detector(mode="balanced"):
    from rtmlib import Body
    body = Body(mode=mode, backend="onnxruntime", device="cpu")
    def run(img):
        kp, sc = body(img[:, :, ::-1].copy())   # rtmlib reads BGR
        if kp is None or len(kp) == 0:
            return None
        best = int(np.argmax(sc.mean(1)))
        return np.asarray(kp[best])[:17, :2]
    return run


def yolo_detector(weights="yolo11m-pose.pt"):
    from ultralytics import YOLO
    m = YOLO(weights)
    def run(img):
        r = m.predict(img[:, :, ::-1].copy(), verbose=False, device="cpu")[0]
        if r.keypoints is None or len(r.keypoints) == 0:
            return None
        conf = r.boxes.conf.cpu().numpy(); best = int(np.argmax(conf))
        return r.keypoints.xy.cpu().numpy()[best][:17]
    return run


OP_TO_COCO = [0, 15, 14, 17, 16, 5, 2, 6, 3, 7, 4, 11, 8, 12, 9, 13, 10]   # OpenPose's 18 (with a neck) -> COCO's 17


def openpose_detector(weights, scales=(0.5, 1.0, 1.5, 2.0)):
    """OpenPose body (CMU's COCO model, PyTorch, CPU), the four scales OpenPose's own evaluation searches; the person
    with the highest total score; a point it does not find counts as missed (scores 0 in OKS)"""
    import sys
    import torch
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor"))
    from openpose.body import Body
    torch.set_num_threads(max(1, torch.get_num_threads()))
    body = Body(str(weights))
    def run(img):
        with torch.inference_mode():
            cand, subset = body(img[:, :, ::-1].copy(), scale_search=list(scales))   # OpenPose reads BGR
        if subset is None or len(subset) == 0:
            return None
        best = subset[int(np.argmax(subset[:, 18]))]
        out = np.full((17, 2), 1e6)
        for c, o in enumerate(OP_TO_COCO):
            i = int(best[o])
            if i >= 0:
                out[c] = cand[i][:2]
        return out
    return run


# Goliath's 308 keypoints -> COCO's 17 (from Sapiens' classes_and_palettes.py): the body points keep COCO's order,
# the wrists sit among the hand points
GOLIATH_TO_COCO = [0, 1, 2, 3, 4, 5, 6, 7, 8, 62, 41, 9, 10, 11, 12, 13, 14]


def sapiens_detector(model_path, box_model=None):
    """Sapiens pose 0.3B (TorchScript, CPU), top-down: the most confident person box from rtmlib's YOLOX (as RTMPose
    gets), padded 1.25x to the model's 3:4 crop (768 x 1024), each COCO point the peak of its heatmap (256 x 192)"""
    import cv2
    import torch
    from rtmlib import Body
    model = torch.jit.load(str(model_path), map_location="cpu").eval()
    det = (box_model or Body(mode="balanced", backend="onnxruntime", device="cpu")).det_model
    mean, std = np.array([123.675, 116.28, 103.53]), np.array([58.395, 57.12, 57.375])
    def run(img):
        boxes = det(img[:, :, ::-1].copy())
        if boxes is None or len(boxes) == 0:
            return None
        x0, y0, x1, y1 = [float(v) for v in boxes[0][:4]]
        cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * 1.25, (y1 - y0) * 1.25
        if w / h > 0.75:
            h = w / 0.75
        else:
            w = h * 0.75
        M = np.array([[768 / w, 0, 384 - cx * 768 / w], [0, 1024 / h, 512 - cy * 1024 / h]])
        crop = cv2.warpAffine(img, M, (768, 1024), flags=cv2.INTER_LINEAR)
        x = torch.from_numpy(((crop - mean) / std).transpose(2, 0, 1)[None].astype(np.float32))
        with torch.inference_mode():
            hm = model(x)[0].numpy()
        out = []
        for k in GOLIATH_TO_COCO:
            iy, ix = np.unravel_index(np.argmax(hm[k]), hm[k].shape)
            px, py = (ix + 0.5) * 4, (iy + 0.5) * 4   # heatmap cell centre in the crop
            out.append([(px - M[0, 2]) / M[0, 0], (py - M[1, 2]) / M[1, 1]])
        return np.array(out)
    return run


def run(bench_json, img_dir, detectors):
    from PIL import Image
    b = json.loads(Path(bench_json).read_text()); out = {}
    for name, make in detectors.items():
        try:
            det = make()
        except Exception as e:   # a detector that cannot load here is reported, not hidden
            out[name] = {"error": str(e)[:300]}; continue
        scores, ts = [], []
        try:
            for it in b["items"]:
                img = np.asarray(Image.open(Path(img_dir) / it["file"]).convert("RGB"))
                t = time.time(); p = det(img); ts.append(time.time() - t)
                scores.append(oks(p, it["kp"], it["area"]))
        except Exception as e:   # one that fails while running is reported too
            out[name] = {"error": f"on image {len(scores) + 1}: {str(e)[:300]}"}; continue
        s = np.array(scores)
        out[name] = {"images": len(s), "mean_oks": round(float(s.mean()), 3), "oks>=0.5": round(float((s >= 0.5).mean()), 3), "oks>=0.75": round(float((s >= 0.75).mean()), 3),
                     "missed": int((s == 0).sum()), "ms_per_image": round(1000 * float(np.median(ts[1:] or ts)), 1)}
    return out
