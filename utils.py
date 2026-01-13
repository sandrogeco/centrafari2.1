import cv2
import numpy as np
import subprocess
import bisect


def get_colore(colore: str):
    if colore == "red":
        return (255, 0, 0)
    if colore == "yellow":
        return (255, 255, 0)
    if colore == "green":
        return (0, 255, 0)
    if colore == "blue":
        return (0, 0, 255)
    if colore == "gold":
        return (255, 215, 0)
    if colore == "cyan":
        return (0, 255, 255)
    if colore == "saddlebrown":
        return (139, 69, 19)
    if colore == "white":
        return (255, 255, 255)
    if colore == "black":
        return (0, 0, 0)
    raise ValueError()


def get_colore_bgr(colore: str):
    return get_colore(colore)[::-1]


def controlla_colore_pixel(pixel, colore):
    colore_rgb = get_colore(colore)
    return (
        pixel[0] == colore_rgb[0]
        and pixel[1] == colore_rgb[1]
        and pixel[2] == colore_rgb[2]
    )


def disegna_pallino(frame, punto, raggio, colore, spessore):
    cv2.circle(frame, punto, raggio, get_colore(colore), spessore, cv2.LINE_AA)


def disegna_segmento(frame, punto1, punto2, spessore, colore):
    cv2.line(
        frame,
        (int(punto1[0]), int(punto1[1])),
        (int(punto2[0]), int(punto2[1])),
        get_colore(colore),
        spessore,
        cv2.LINE_AA
    )


def disegna_croce(frame, punto, larghezza, spessore, colore):
    disegna_segmento(
        frame,
        (punto[0] - larghezza, punto[1]),
        (punto[0] + larghezza, punto[1]),
        spessore,
        colore,
    )
    disegna_segmento(
        frame,
        (punto[0], punto[1] - larghezza),
        (punto[0], punto[1] + larghezza),
        spessore,
        colore,
    )


def disegna_croci(frame, punti, larghezza, spessore, colore):
    for punto in punti:
        disegna_croce(frame, punto, larghezza, spessore, colore)


def disegna_linea(frame, punti, spessore, colore):
    for i in range(0, len(punti) - 1):
        disegna_segmento(frame, punti[i], punti[i + 1], spessore, colore)

def disegna_linea_inf(frame, punti, spessore, colore):
    m=(punti[1][1]-punti[0][1])/(punti[1][0]-punti[0][0])
    q=punti[0][1]-m*punti[0][0]
    if punti[1][0]>punti[0][0]:
        disegna_segmento(frame, (0,q), punti[1], spessore, colore)
    else:
        disegna_segmento(frame, (frame.shape[1],m*frame.shape[1]+q), punti[1], spessore, colore)

def disegna_linea_angolo(frame,punto,angolo,spessore,colore):
    m=np.tan(np.deg2rad(angolo))
   # q = punto[1] - m * punto[0]
    if (angolo>90)and(angolo<270):
        x=0
    else:
        x=frame.shape[1]
    disegna_segmento(frame, punto,(x,- m*(x-punto[0])+punto[1]), spessore, colore)



def disegna_rettangolo(frame, punto_ll, punto_ur, spessore, colore):
    min_x = punto_ll[0]
    max_x = punto_ur[0]
    min_y = punto_ll[1]
    max_y = punto_ur[1]
    disegna_segmento(frame, (min_x, min_y), (max_x, min_y), spessore, colore)
    disegna_segmento(frame, (min_x, min_y), (min_x, max_y), spessore, colore)
    disegna_segmento(frame, (min_x, max_y), (max_x, max_y), spessore, colore)
    disegna_segmento(frame, (max_x, min_y), (max_x, max_y), spessore, colore)


def find_y_by_x(contour, x):
    c = contour[:, 0, :]
    pos = bisect.bisect_left(c[:, 0], x)

    if pos == 0:
        return c[0][1]
    elif pos == len(c):
        return c[-1][1]
    else:
        before, after = c[pos - 1], c[pos]
        return after[1] if (after[0] - x) < (x - before[0]) else before[1]


def somma_vettori(v1, v2):
    return (v1[0] + v2[0], v1[1] + v2[1])


def differenza_vettori(v1, v2):
    return (v1[0] - v2[0], v1[1] - v2[1])


def angolo_vettori(v1, v2):
    x1, y1 = v1
    x2, y2 = v2

    dot = x1 * x2 + y1 * y2
    det = x1 * y2 - y1 * x2
    return np.arctan2(det, dot) * 180 / np.pi


def angolo_esterno_vettori(v1, v2):
    return angolo_vettori(differenza_vettori((0, 0), v1), v2)


def uccidi_processo(cmd):
    subprocess.Popen(f"echo 1234 | sudo -S pkill -15 -f '{cmd}'", shell=True)
