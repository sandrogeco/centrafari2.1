#!/bin/bash
# Controlla stato autoexp in tempo reale
cd /home/pi/Applications/MW28912
python3 - <<'EOF'
import cv2, numpy as np, json, time

with open('config.json') as f:
    cfg = json.load(f)

setpoint = cfg.get('autoexp_setpoint', 237)
tol = cfg.get('autoexp_stable_tol', 5)
perc_target = cfg.get('autoexp_perc_target', 0.5)
perc_tol = cfg.get('autoexp_perc_tol', 0.3)
cx, cy = cfg['crop_center']
cw, ch = cfg['crop_w'], cfg['crop_h']
x0 = max(0, cx - cw//2)
y0 = max(0, cy - ch//2)

print(f"setpoint={setpoint} tol={tol} range=[{setpoint-tol},{setpoint+tol}]")
print(f"perc_target={perc_target}% perc_tol={perc_tol}%")
print(f"crop: x={x0}-{x0+cw} y={y0}-{y0+ch}")
print("-" * 50)

import subprocess
while True:
    img = cv2.imread('/tmp/frame.jpg', cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("frame non disponibile")
        time.sleep(1)
        continue
    crop = img[y0:y0+ch, x0:x0+cw]
    valid = crop[crop < 255]
    r = np.max(valid) if len(valid) > 0 else 255
    in_range = np.sum((crop >= setpoint - tol) & (crop <= setpoint + tol))
    perc = in_range / crop.size * 100
    perc_ok = abs(perc - perc_target) <= perc_tol
    res = subprocess.run(['v4l2-ctl','--device','/dev/video0','--get-ctrl=exposure_absolute'],
                         capture_output=True, text=True)
    exp = res.stdout.strip().split(':')[-1].strip()
    ok_str = "OK" if perc_ok else "--"
    print(f"max:{r:3.0f}  in_range:{in_range:5d}  perc:{perc:.3f}%  target:{perc_target}±{perc_tol}%  exp:{exp}  [{ok_str}]")
    time.sleep(0.5)
EOF
