"""Key sampling as the player plays it (Acting.sampleKeys and Acting.ease in puppet/loader/acting.js), for the Python
side: Blender's camera (dbe/blender_gn.py) and tests. No dependencies, so Blender's own Python can load it by path."""


def ease(k, e):
    """Acting.ease: smooth (smoothstep), linear, hold or a cubic Bezier [x1, y1, x2, y2] solved by bisection"""
    if not e or e == "smooth":
        return k * k * (3 - 2 * k)
    if e == "linear":
        return k
    if e == "hold":
        return 1.0 if k >= 1 else 0.0
    x1, y1, x2, y2 = e
    B = lambda u, a, b: 3 * a * u * (1 - u) ** 2 + 3 * b * u * u * (1 - u) + u ** 3
    lo, hi = 0.0, 1.0
    for _ in range(40):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if B(m, x1, x2) < k else (lo, m)
    return B((lo + hi) / 2, y1, y2)


def sample_keys(keys, t):
    """the player's camera keys as Acting.sampleKeys plays them (smoothstep unless a key sets its easing)"""
    if t <= keys[0][0]:
        return keys[0][1]
    for a, b in zip(keys, keys[1:]):
        t0, v0, t1, v1 = a[0], a[1], b[0], b[1]
        if t <= t1:
            k = ease(min(1, max(0, (t - t0) / ((t1 - t0) or 1))), a[2] if len(a) > 2 else None)
            return [x + (y - x) * k for x, y in zip(v0, v1)]
    return keys[-1][1]
