"""Pose detectors compared by measured accuracy (WP-12): MediaPipe Pose Landmarker (what act-out uses), RTMPose via
rtmlib, and Ultralytics YOLO11-pose, on single-person photos from COCO val2017 with their annotated keypoints.

Score: COCO's Object Keypoint Similarity (OKS, its per-keypoint sigmas, over the annotated keypoints, the person's
area as scale) per image, the share of images with OKS >= 0.5 and >= 0.75 (as COCO's AP thresholds, here per image:
one person each), the mean OKS, and the CPU time per image. MediaPipe's 33 landmarks map onto COCO's 17.
OpenPose (a Caffe build) and Sapiens (0.3 to 2 billion parameters) are not run here: noted as such.
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
