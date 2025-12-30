import cv2
import sys
import numpy as np
from typing import Tuple
from scipy.optimize import curve_fit
from funcs_misc import is_punto_ok,draw_polyline_aa
import logging

from utils import disegna_pallino


# 1. Preprocessing: blur + Otsu + Canny
def preprocess(gray: np.ndarray,
               blur_ksize: int = 5,
               canny_lo: int = 40,
               canny_hi: int = 120) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 0)

   # tr, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, binary = cv2.threshold(blur, 25, 255, cv2.THRESH_BINARY)

    binary[0:5,:]=0
    binary[-5:, :] = 0
    binary[:, 0:5] = 0
    binary[:, -5:] = 0

    edges = cv2.Canny(binary, canny_lo, canny_hi, apertureSize=3)

    return edges,binary

# 2. Extract contour points
def extract_contour_points(edges: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise ValueError("No contours found")
    largest = max(contours, key=cv2.contourArea)
    pts = np.squeeze(largest)
    return pts.astype(float),contours

# 3. Two-line model for curve_fit
def two_lines(x: np.ndarray,
              X0: float, Y0: float,
              mo: float, mi: float) -> np.ndarray:
    if (mi>mo): #y up =0!!
        return np.full_like(x,1e6)
    y = np.where(x <= X0,
                 Y0 + mo * (x - X0),
                 Y0 + mi * (x - X0))
    # Dynamic visualization of current fit line


    return y


def one_lines(x: np.ndarray,
              X0: float, Y0: float,
              mo: float) -> np.ndarray:


    y=mo*(x-X0)+Y0

    return y



def fit_lines(image_input,image_output,cache,
              blur_ksize: int = 5,
              canny_lo: int = 40,
              canny_hi: int = 120,
              ftol: float = 1e-7,
              xtol: float = 1e-7,
              maxfev: int = 1000,
              debug: bool = False,
              flat:bool=False) -> None:
    global gray, x_data, y_data

    edges,binary = preprocess(image_input, blur_ksize, canny_lo, canny_hi)

    try:
        pts,ctrs = extract_contour_points(edges)
        if ctrs:
            largest = max(ctrs, key=cv2.contourArea)
            cv2.drawContours(image_output, [largest], -1, (0,0,255), 1,lineType=cv2.LINE_AA)

        leftset_upper=pts[np.lexsort((pts[:, 1], pts[:, 0]))]
        rightest_upper=pts[np.lexsort((pts[:, 0], pts[:, 1]))]
        y_h=leftset_upper[0][1]
        if flat:
            x_min=np.min(pts[:,0])
            x_max = np.max(pts[:, 0])
        else:
            x_min=leftset_upper[0][0]
            x_max=rightest_upper[0][0]
      #  margin = (x_max - x_min) * margin_frac
        try:
            marginl=cache['margin_auto']
        except:
            marginl=0
            marginl1=0
            cache['margin_auto']=0
            cache['s_err']=np.Inf
            cache['X0']=300
            cache['Y0']=0
            cache['r_bound']=x_max

        if cache['autoexp']:
            #marginl=0
            cache['margin_auto']=0
            cache['s_err']=np.Inf
            cache['r_bound'] = x_max
        marginl=10
        left_bound = x_min + marginl
        right_bound =np.minimum(x_max,cache['r_bound'])-marginl#x_max -marginl#cache['X0']+(cache['X0']-left_bound)
        logging.debug(f"cachex0:{cache['X0']}")
        logging.debug(f"left_bound:{left_bound}")
        logging.debug(f"right_bound:{right_bound}")
        logging.debug(f"x_max:{x_max}")
        mask = (pts[:,0] >= left_bound) & (pts[:,0] <= right_bound)
        pts_mask= pts[mask]

        top_pts = pts_mask[pts_mask[:,1] <= y_h]
        bot_pts = pts_mask[pts_mask[:,1] >  y_h]
        # draw both pieces
       # canvas = cv2.cvtColor(image_input, cv2.COLOR_GRAY2BGR)
#        for x,y in top_pts.astype(int): cv2.circle(image_output,(x,y),1,(255,0,255),-1)
#        for x,y in bot_pts.astype(int): cv2.circle(image_output,(x,y),1,(0,255,0),-1)
        if debug:
            cv2.imshow('Contour split', image_output)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        # keep only top for fitting
        pts = top_pts
        x_data = pts[:, 0]
        y_data = pts[:, 1]




        if flat:
            p0 = [np.mean(x_data), np.max(y_data) - 1, -0.01]
           # xm=(np.max(x_data)+np.min(x_data))/2
            bounds = (
                [np.min(x_data), 0.0, -np.Inf],
                [np.max(x_data), np.max(y_data),np.Inf]
            )
            try:
                popt, _ = curve_fit(
                    one_lines, x_data, y_data,
                    p0=p0, bounds=bounds,
                    ftol=ftol, xtol=xtol, maxfev=maxfev
                )
                X0, Y0, mo= popt
                X0=int((np.max(x_data)+np.min(x_data))/2)
                mi=0
            except Exception as e:
                cv2.putText(image_output, str(e), (5, 100), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, (0, 255, 0), 1)


        else:
            p0 = [np.mean(x_data), np.max(y_data) - 1, -0.01, -1.0]
            bounds = (
                [np.min(x_data), 0.0, -0.5, -np.Inf],
                [np.max(x_data), np.max(y_data), 0, 0]
            )
            try:
                popt, _ = curve_fit(
                    two_lines, x_data, y_data,
                    p0=p0, bounds=bounds,
                    ftol=ftol, xtol=xtol, maxfev=maxfev
                )
                X0, Y0, mo, mi= popt

            except Exception as e:
                cv2.putText(image_output, str(e), (5, 100), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.5, (0, 255, 0), 1)


        h, w = image_input.shape
        xs = np.array([0, X0,w])
        ys=two_lines(xs,X0,Y0,mo,mi)
        cv2.line(image_output, (int(round(xs[0])), int(round(ys[0]))), (int(round(xs[1])), int(round(ys[1]))), (0,255,255), 1,lineType=cv2.LINE_AA)
        cv2.line(image_output, (int(round(xs[1])), int(round(ys[1]))), (int(round(xs[2])), int(round(ys[2]))), (0, 255, 255), 1,lineType=cv2.LINE_AA)
        ptok=is_punto_ok((X0,Y0),cache)
        if ptok:
            color=(0,255,0)
        else:
            color=(255,0,0)
        cv2.circle(image_output,(int(round(X0)),int(round(Y0))),2,color,2,-1)
        for p in top_pts:
            image_output[int(p[1]),int(p[0])]=0
        #img_temp=image_output.copy()*0
        [cv2.circle(image_output, (int(p[0]),int(p[1])), 1, color, 1, lineType=cv2.LINE_AA) for p in top_pts]
        #img_temp= cv2.GaussianBlur(img_temp, (0, 0), 1.5)
      #  image_output=image_output+img_temp
        #image_output[img_temp>0]=img_temp[img_temp>0]
       # image_output = cv2.normalize(image_output, None, 0, 255, cv2.NORM_MINMAX)
      #  [cv2.circle(image_output, (int(p[0])-1, int(p[1])-1), 1, (255,0,0), 1, lineType=cv2.LINE_AA) for p in top_pts]
        #draw_polyline_aa(image_output,top_pts,color)

        #[cv2.circle(image_output,(e[0],e[1]),1,(255,0,0),-1) for e in edges]
#        ctrs, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)


        cache['X0'] = X0
        cache['Y0'] = Y0
        try:
            dx = (X0 - cache['config']['width'] / 2) / cache['stato_comunicazione']['qin']
            dy = (Y0 - cache['config']['height'] / 2 + cache['stato_comunicazione']['inclinazione']) /cache['stato_comunicazione']['qin']
            yaw_deg = np.degrees(np.arctan2(dx, 25))  # rotazione orizzontale (destra/sinistra)
            pitch_deg = np.degrees(np.arctan2(dy, 25))
            roll_deg = np.degrees(np.arctan(mo))
        except:
            yaw_deg = 0
            roll_deg = 0
            pitch_deg = 0


    except Exception as e:
        X0=0
        Y0=0
        mo=0
        yaw_deg=0
        roll_deg=0
        pitch_deg=0
      #  logging.error(e)

    

    return image_output,(X0,Y0),(yaw_deg,pitch_deg,roll_deg)

    #print(f"Fit completed: X0={X0:.2f}, Y0={Y0:.2f}, mo={mo:.4f}, mi={mi:.4f}")

if False:#__name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Fit two lines to contour')
    parser.add_argument('image', help='Path to grayscale image')
    parser.add_argument('--blur', type=int, default=5)
    parser.add_argument('--canny-lo', type=int, default=40)
    parser.add_argument('--canny-hi', type=int, default=120)
    parser.add_argument('--ftol', type=float, default=1e-8, help='ftol for curve_fit')
    parser.add_argument('--xtol', type=float, default=1e-8, help='xtol for curve_fit')
    parser.add_argument('--maxfev', type=int, default=1000, help='maxfev for curve_fit')
    parser.add_argument('--no-debug', action='store_true')
    args = parser.parse_args()
    #fit lines(image, 5,40,120,1e-8,1e-8,1000)
    fit_lines(
        args.image,
        blur_ksize=args.blur,
        canny_lo=args.canny_lo,
        canny_hi=args.canny_hi,
        ftol=args.ftol,
        xtol=args.xtol,
        maxfev=args.maxfev,
        debug=not args.no_debug
    )
