import os
import math
from typing import List, Dict, Tuple, Optional, Any
FACECAM_QUADRANTS: Dict[str, str] = {
    "top-right": "0.68,0.05,0.28,0.22",
    "top-left": "0.04,0.05,0.28,0.22",
    "bottom-left": "0.04,0.72,0.28,0.22",
    "bottom-right": "0.68,0.72,0.28,0.22",
}
DEFAULT_FACECAM_BOX = FACECAM_QUADRANTS["top-right"]


def auto_detect_facecam_quadrant(video_path: str, sample_frames: int = 5) -> Tuple[str, str]:
    """
    Detects which quadrant the streamer facecam is located in by sampling keyframes.
    Returns (quadrant_name, normalized_box_string).
    Falls back to ('top-right', FACECAM_QUADRANTS['top-right']) if no faces detected or error.
    """
    fallback = ("top-right", FACECAM_QUADRANTS["top-right"])
    if not video_path or not os.path.exists(video_path):
        return fallback

    try:
        import cv2
    except ImportError:
        return fallback

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return fallback

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if total_frames <= 0 or width <= 0 or height <= 0:
            cap.release()
            return fallback

        num_samples = max(1, sample_frames)
        step = total_frames / (num_samples + 1)
        frame_indices = [int((i + 1) * step) for i in range(num_samples)]

        face_cascade = None
        if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
            if os.path.exists(cascade_path):
                try:
                    face_cascade = cv2.CascadeClassifier(cascade_path)
                except Exception:
                    face_cascade = None

        insight_app = None
        if face_cascade is None:
            try:
                from scripts.face_detection_insightface import init_insightface
                insight_app = init_insightface()
            except Exception:
                insight_app = None

        votes: Dict[str, int] = {"top-right": 0, "top-left": 0, "bottom-left": 0, "bottom-right": 0}

        for f_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, min(f_idx, total_frames - 1))
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            detected_centers = []
            if face_cascade is not None:
                try:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    det_faces = face_cascade.detectMultiScale(gray, 1.1, 3, minSize=(20, 20))
                    for fx, fy, fw, fh in det_faces:
                        cx = (fx + fw / 2.0) / width
                        cy = (fy + fh / 2.0) / height
                        detected_centers.append((cx, cy))
                except Exception:
                    pass

            if not detected_centers and insight_app is not None:
                try:
                    faces = insight_app.get(frame)
                    for f in faces:
                        cx = ((f.bbox[0] + f.bbox[2]) / 2.0) / width
                        cy = ((f.bbox[1] + f.bbox[3]) / 2.0) / height
                        detected_centers.append((cx, cy))
                except Exception:
                    pass

            for cx, cy in detected_centers:
                if cx >= 0.5 and cy < 0.5:
                    votes["top-right"] += 1
                elif cx < 0.5 and cy < 0.5:
                    votes["top-left"] += 1
                elif cx < 0.5 and cy >= 0.5:
                    votes["bottom-left"] += 1
                else:
                    votes["bottom-right"] += 1

        cap.release()
        max_votes = max(votes.values())
        if max_votes > 0:
            winner = max(votes, key=votes.get)
            return winner, FACECAM_QUADRANTS[winner]

        return fallback
    except Exception:
        try:
            cap.release()
        except Exception:
            pass
        return fallback


def auto_detect_facecam_box(video_path: str, sample_sec: float = 5.0) -> str:
    """
    Returns normalized facecam crop box string for video_path by detecting face quadrant.
    """
    _quadrant, box_str = auto_detect_facecam_quadrant(video_path)
    return box_str
def _safe_float(val: Any, default: Optional[float] = 0.0) -> Optional[float]:
    """Safely converts input to float, guarding against None, bool, NaN, and Inf."""
    if val is None or isinstance(val, bool):
        return default
    try:
        res = float(val)
        if math.isnan(res) or math.isinf(res):
            return default
        return res
    except (ValueError, TypeError):
        return default

def compute_mouth_aspect_ratio(landmarks: List[Tuple[float, float]]) -> float:
    """
    Computes Mouth Aspect Ratio (MAR) from 4 or 5 landmark coordinates:
    landmarks[0]: left corner, landmarks[1]: right corner,
    landmarks[2]: top lip, landmarks[3]: bottom lip.
    MAR = height / width.
    """
    if landmarks is None:
        return 0.0

    try:
        if len(landmarks) < 4:
            return 0.0
        left = landmarks[0]
        right = landmarks[1]
        top = landmarks[2]
        bottom = landmarks[3]

        lx = _safe_float(left[0], None)
        ly = _safe_float(left[1], None)
        rx = _safe_float(right[0], None)
        ry = _safe_float(right[1], None)
        tx = _safe_float(top[0], None)
        ty = _safe_float(top[1], None)
        bx = _safe_float(bottom[0], None)
        by = _safe_float(bottom[1], None)

        if None in (lx, ly, rx, ry, tx, ty, bx, by):
            return 0.0

        width = math.sqrt((rx - lx) ** 2 + (ry - ly) ** 2)
        height = math.sqrt((bx - tx) ** 2 + (by - ty) ** 2)

        if width <= 1e-4:
            return 0.0

        mar = height / width
        if math.isnan(mar) or math.isinf(mar) or mar < 0.0:
            return 0.0

        return round(mar, 3)
    except (IndexError, TypeError, ValueError):
        return 0.0


def score_facecam_reaction(mar: float, motion_velocity: float) -> float:
    """
    Scores facecam reaction intensity out of 100 based on mouth opening and head movement.
    MAR > 0.12 triggers high score; velocity > 15.0 px/frame adds body movement bonus.
    """
    mar_val = max(0.0, _safe_float(mar, 0.0) or 0.0)
    vel_val = max(0.0, _safe_float(motion_velocity, 0.0) or 0.0)

    if mar_val >= 0.12:
        mar_score = min(60.0, 30.0 + (mar_val - 0.12) * 250.0)
    else:
        mar_score = max(0.0, mar_val * 200.0)

    motion_score = 0.0
    if vel_val > 3.0:
        motion_score = (vel_val - 3.0) * 1.5
        if vel_val > 15.0:
            motion_score += 10.0
        motion_score = min(40.0, max(0.0, motion_score))

    total = min(100.0, max(0.0, mar_score + motion_score))
    return round(total, 1)


def detect_facecam_reactions(
    video_path: str,
    facecam_box_str: Optional[str] = None,
    candidate_timestamps: Optional[List[float]] = None
) -> List[Dict[str, Any]]:
    """
    Extracts facecam frames around candidate_timestamps (or scans stream) and detects reactions.
    Gracefully returns [] if video is missing, or fallback neutral reactions if facecam box
    is missing or OpenCV/InsightFace detects no faces.
    """
    if not video_path or not isinstance(video_path, str) or not os.path.exists(video_path):
        return []

    if candidate_timestamps is None:
        return []

    try:
        clean_ts = []
        for ts in candidate_timestamps:
            v = _safe_float(ts, None)
            if v is not None and v >= 0.0:
                clean_ts.append(round(v, 2))
    except (TypeError, Exception):
        return []

    clean_ts = sorted(set(clean_ts))
    if not clean_ts:
        return []
    fallback_reactions = [
        {
            "timestamp": ts,
            "mar": 0.05,
            "motion_velocity": 0.0,
            "score": 0.0,
        }
        for ts in clean_ts
    ]

    try:
        import cv2
    except ImportError:
        return fallback_reactions

    if facecam_box_str is None or str(facecam_box_str).strip().lower() in ("auto", "none"):
        facecam_box_str = auto_detect_facecam_box(video_path)

    try:
        from scripts.gaming_split import parse_normalized_box
        x_norm, y_norm, w_norm, h_norm = parse_normalized_box(facecam_box_str)
    except Exception:
        x_norm, y_norm, w_norm, h_norm = 0.0, 0.0, 0.5, 0.5

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return fallback_reactions
    except Exception:
        return fallback_reactions

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        if fps <= 0.0 or math.isnan(fps):
            fps = 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        px_x = int(round(x_norm * width)) if width > 0 else 0
        px_y = int(round(y_norm * height)) if height > 0 else 0
        px_w = max(1, int(round(w_norm * width))) if width > 0 else 1
        px_h = max(1, int(round(h_norm * height))) if height > 0 else 1

        insight_app = None
        try:
            from scripts.face_detection_insightface import init_insightface
            insight_app = init_insightface()
        except Exception:
            insight_app = None

        face_cascade = None
        if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
            if os.path.exists(cascade_path):
                try:
                    face_cascade = cv2.CascadeClassifier(cascade_path)
                except Exception:
                    face_cascade = None

        reactions = []
        for ts in clean_ts:
            center_frame = int(round(ts * fps))
            sample_offsets = [-2, -1, 0, 1, 2]

            sampled_frames = []
            for off in sample_offsets:
                f_idx = max(0, center_frame + off)
                if total_frames > 0 and f_idx >= total_frames:
                    f_idx = max(0, total_frames - 1)
                cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                ret, frame = cap.read()
                if ret and frame is not None:
                    if height > 0 and width > 0:
                        crop = frame[px_y:px_y + px_h, px_x:px_x + px_w]
                        if crop.size > 0:
                            sampled_frames.append(crop)
                        else:
                            sampled_frames.append(frame)
                    else:
                        sampled_frames.append(frame)

            if not sampled_frames:
                reactions.append({
                    "timestamp": ts,
                    "mar": 0.05,
                    "motion_velocity": 0.0,
                    "score": 0.0,
                })
                continue

            face_centers = []
            mars = []

            for crop_img in sampled_frames:
                face_detected = False
                if insight_app is not None:
                    try:
                        faces = insight_app.get(crop_img)
                        if faces:
                            best_face = max(
                                faces,
                                 key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
                            )
                            cx = (best_face.bbox[0] + best_face.bbox[2]) / 2.0
                            cy = (best_face.bbox[1] + best_face.bbox[3]) / 2.0
                            face_centers.append((cx, cy))
                            face_detected = True

                            if hasattr(best_face, "landmarks") and best_face.landmarks is not None:
                                mar_val = compute_mouth_aspect_ratio(best_face.landmarks)
                                mars.append(mar_val)
                            elif hasattr(best_face, "kps") and best_face.kps is not None and len(best_face.kps) >= 5:
                                left_m = best_face.kps[3]
                                right_m = best_face.kps[4]
                                mouth_center_x = (left_m[0] + right_m[0]) / 2.0
                                mouth_center_y = (left_m[1] + right_m[1]) / 2.0
                                approx_landmarks = [
                                    (float(left_m[0]), float(left_m[1])),
                                    (float(right_m[0]), float(right_m[1])),
                                    (float(mouth_center_x), float(mouth_center_y - 5.0)),
                                    (float(mouth_center_x), float(mouth_center_y + 5.0)),
                                ]
                                mar_val = compute_mouth_aspect_ratio(approx_landmarks)
                                mars.append(mar_val)
                    except Exception:
                        pass

                if not face_detected and face_cascade is not None:
                    try:
                        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
                        det_faces = face_cascade.detectMultiScale(gray, 1.1, 3)
                        if len(det_faces) > 0:
                            fx, fy, fw, fh = det_faces[0]
                            cx = fx + fw / 2.0
                            cy = fy + fh / 2.0
                            face_centers.append((cx, cy))
                            face_detected = True
                    except Exception:
                        pass

            if not face_centers:
                reactions.append({
                    "timestamp": ts,
                    "mar": 0.05,
                    "motion_velocity": 0.0,
                    "score": 0.0,
                })
                continue

            displacements = []
            for k in range(1, len(face_centers)):
                d = math.sqrt(
                    (face_centers[k][0] - face_centers[k - 1][0]) ** 2
                    + (face_centers[k][1] - face_centers[k - 1][1]) ** 2
                )
                displacements.append(d)

            motion_velocity = max(displacements) if displacements else 0.0
            mar = max(mars) if mars else 0.05
            reaction_score = score_facecam_reaction(mar=mar, motion_velocity=motion_velocity)

            reactions.append({
                "timestamp": ts,
                "mar": round(mar, 3),
                "motion_velocity": round(motion_velocity, 2),
                "score": reaction_score,
            })

        cap.release()
        return reactions
    except Exception:
        try:
            cap.release()
        except Exception:
            pass
        return fallback_reactions
