# emotion_detection.py
# PART 1 — Core Detection Engine
#
# Responsibility: Open the webcam, grab a frame, and use DeepFace to
# identify the dominant facial emotion.
#
# This part has NO Pepper or voice logic — it only detects and reports.
# Voice responses and Pepper integration come in Part 2 and Part 3.
#
# Dependencies:
#   pip install opencv-python deepface tf-keras
#
# Run standalone to test:
#   python emotion_detection.py

import cv2
from deepface import DeepFace


# ---------------------------------------------------------------------------
# 1. CAMERA — grab a single frame from the webcam
# ---------------------------------------------------------------------------

def capture_frame(camera_index: int = 0):
    """
    Open the webcam at `camera_index`, read one frame, and release the camera.

    We discard the first 3 frames because many USB/built-in cameras produce
    dark or blurry images right after they open — the sensor needs a moment
    to adjust its exposure.

    Parameters
    ----------
    camera_index : int
        0 = first available camera (built-in or USB).
        Change to 1, 2 … if you have multiple cameras.

    Returns
    -------
    numpy.ndarray (BGR image) if successful, or None on failure.
    """
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"[EMOTION] ERROR: Cannot open camera index {camera_index}.")
        return None

    # Warm-up: skip the first 3 dark/blurry startup frames
    for _ in range(3):
        cap.read()

    ret, frame = cap.read()
    cap.release()   # always release — don't leave the camera locked

    if not ret or frame is None:
        print("[EMOTION] ERROR: Failed to read frame from camera.")
        return None

    print(f"[EMOTION] Frame captured — shape: {frame.shape}")   # (height, width, 3)
    return frame


# ---------------------------------------------------------------------------
# 2. ANALYSIS — run DeepFace to extract emotion from the frame
# ---------------------------------------------------------------------------

def analyse_emotion(frame) -> dict | None:
    """
    Pass the captured frame to DeepFace and extract emotion data.

    DeepFace runs a pre-trained CNN (default: mini_XCEPTION model) and
    returns a confidence percentage for each of 7 emotions:
        angry, disgust, fear, happy, neutral, sad, surprise

    The emotion with the highest percentage becomes the `dominant_emotion`.

    Parameters
    ----------
    frame : numpy.ndarray
        BGR image array returned by capture_frame().

    Returns
    -------
    dict with keys:
        - emotion       (str)   dominant emotion label
        - confidence    (float) percentage confidence, 0–100
        - face_count    (int)   how many faces were detected
        - all_scores    (dict)  full emotion → confidence map
    or None if no face was detected or DeepFace raised an exception.
    """
    try:
        # enforce_detection=False → return gracefully (not raise) if no face found
        # silent=True            → suppress DeepFace's own progress bar prints
        results = DeepFace.analyze(
            img_path=frame,
            actions=["emotion"],        # we only need emotion, skip age/gender/race
            enforce_detection=False,
            silent=True,
        )

        # DeepFace returns a list (one dict per face found)
        if not results:
            print("[EMOTION] No face detected in frame.")
            return None

        # Take the first (most prominent) face
        face_data        = results[0] if isinstance(results, list) else results
        dominant_emotion = face_data["dominant_emotion"]
        all_scores       = face_data["emotion"]             # {emotion: confidence}
        confidence       = all_scores.get(dominant_emotion, 0.0)
        face_count       = len(results) if isinstance(results, list) else 1

        return {
            "emotion":    dominant_emotion,
            "confidence": round(confidence, 2),
            "face_count": face_count,
            "all_scores": all_scores,
        }

    except Exception as e:
        print(f"[EMOTION] ERROR during DeepFace analysis: {e}")
        return None


# ---------------------------------------------------------------------------
# 3. PRINT — display the result in a readable format
# ---------------------------------------------------------------------------

def print_emotion_result(result: dict):
    """
    Pretty-print the emotion analysis result to the console.

    Parameters
    ----------
    result : dict
        The dict returned by analyse_emotion().
    """
    print()
    print("=" * 45)
    print(f"  Faces detected : {result['face_count']}")
    print(f"  Dominant emotion : {result['emotion'].upper()}")
    print(f"  Confidence       : {result['confidence']:.1f}%")
    print()
    print("  All emotion scores:")
    # Sort by confidence descending so the top emotion is first
    sorted_scores = sorted(
        result["all_scores"].items(),
        key=lambda x: x[1],
        reverse=True,
    )
    for emotion, score in sorted_scores:
        bar = "█" * int(score / 5)   # simple ASCII bar (max 20 chars at 100%)
        print(f"    {emotion:<10} {score:5.1f}%  {bar}")
    print("=" * 45)
    print()


# ---------------------------------------------------------------------------
# 4. MAIN — standalone demo
# ---------------------------------------------------------------------------

def detect_once(camera_index: int = 0) -> dict | None:
    """
    High-level helper: capture + analyse + print in one call.

    Returns the result dict, or None if the camera or face detection failed.
    This function will be imported and used by Part 2 (voice logic) and
    Part 3 (Pepper integration).
    """
    frame = capture_frame(camera_index)
    if frame is None:
        return None

    result = analyse_emotion(frame)
    if result is None:
        print("[EMOTION] Could not determine emotion (no face in frame?).")
        return None

    print_emotion_result(result)
    return result


if __name__ == "__main__":
    import time

    print("=" * 45)
    print("  Emotion Detection — Part 1: Core Engine")
    print("=" * 45)
    print()
    print("Scanning your face every 3 seconds.")
    print("Press Ctrl-C to stop.")
    print()

    while True:
        detect_once(camera_index=0)
        time.sleep(3)
