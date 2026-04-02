# emotion_detection.py
# PART 1 — Core Detection Engine  (camera capture + DeepFace analysis)
# PART 2 — Voice & Response Logic (voice profiles + scripted responses)
#
# Part 3 (Pepper integration + continuous background thread) comes next.
#
# Dependencies:
#   pip install opencv-python deepface tf-keras
#
# Run standalone to test:
#   python emotion_detection.py

import cv2
import random
from deepface import DeepFace


# ===========================================================================
# PART 1 — CORE DETECTION ENGINE
# ===========================================================================

# ---------------------------------------------------------------------------
# 1a. CAMERA — grab a single frame from the webcam
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
# 1b. ANALYSIS — run DeepFace to extract emotion from the frame
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
# 1c. PRINT — display the result in a readable format
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
    print(f"  Faces detected   : {result['face_count']}")
    print(f"  Dominant emotion : {result['emotion'].upper()}")
    print(f"  Confidence       : {result['confidence']:.1f}%")
    print()
    print("  All emotion scores:")
    # Sort by confidence descending so the top emotion appears first
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
# 1d. HIGH-LEVEL HELPER — capture + analyse + print in one call
# ---------------------------------------------------------------------------

def detect_once(camera_index: int = 0) -> dict | None:
    """
    Capture one frame, detect emotion, print result, and return the dict.

    This function is imported and used by Part 3 (Pepper integration).
    Returns None if the camera or face detection failed.
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


# ===========================================================================
# PART 2 — VOICE & RESPONSE LOGIC
# ===========================================================================

# ---------------------------------------------------------------------------
# 2a. VOICE PROFILES
#     Maps each emotion to pitch and speed multipliers that shape how
#     Pepper sounds when it speaks.
#
#     pitch < 1.0  →  deeper / calmer voice
#     pitch > 1.0  →  higher / brighter voice
#     speed < 1.0  →  slower, giving the customer more space
#     speed > 1.0  →  faster, more energetic
#
#     On real Pepper hardware these values feed into NAOqi's
#     ALTextToSpeech service:
#         tts.setParameter("pitchShift", profile["pitch"])
#         tts.setParameter("speed",      profile["speed"] * 100)
# ---------------------------------------------------------------------------

VOICE_PROFILES = {
    "angry": {
        "pitch":       0.80,   # lower pitch — calm, not confrontational
        "speed":       0.85,   # slower — gives the customer space
        "description": "calm and reassuring",
    },
    "sad": {
        "pitch":       0.90,   # slightly lower — empathetic
        "speed":       0.90,   # gentle pace
        "description": "warm and encouraging",
    },
    "fear": {
        "pitch":       0.95,
        "speed":       0.85,
        "description": "calm and reassuring",
    },
    "disgust": {
        "pitch":       0.85,
        "speed":       0.90,
        "description": "calm and helpful",
    },
    "surprise": {
        "pitch":       1.05,   # slightly higher — matches their energy
        "speed":       1.05,
        "description": "upbeat and engaging",
    },
    "happy": {
        "pitch":       1.10,   # brighter voice — match the happy mood
        "speed":       1.10,
        "description": "cheerful and energetic",
    },
    "neutral": {
        "pitch":       1.00,   # natural default voice
        "speed":       1.00,
        "description": "friendly and natural",
    },
}


# ---------------------------------------------------------------------------
# 2b. EMOTION RESPONSES
#     Scripted lines Pepper can say for each emotion.
#     random.choice() picks one each time so Pepper doesn't repeat itself.
#     All lines are written to be short, human, and non-corporate.
# ---------------------------------------------------------------------------

EMOTION_RESPONSES = {
    "angry": [
        "I'm really sorry if something has upset you. "
        "I'm here to make your visit as smooth as possible — what can I help you with?",
        "I can see you might be frustrated. "
        "Let me do my best to sort things out for you right away.",
        "Your time is valuable. "
        "Let me take care of things quickly so you can be on your way.",
    ],
    "sad": [
        "It looks like you might be having a tough day. "
        "I hope I can brighten it up a little — what do you need?",
        "I'm here for you. "
        "Let me know how I can help and I'll do my very best.",
        "Sometimes a little treat can help. "
        "Can I suggest something nice from our store today?",
    ],
    "fear": [
        "Please don't worry — I'm here to help and everything is under control. "
        "What can I do for you?",
        "Take your time. I'm right here whenever you're ready.",
    ],
    "disgust": [
        "I'm sorry if something isn't up to standard. "
        "Please let me know and we'll fix it immediately.",
        "Your feedback matters to us. "
        "How can I make your experience better today?",
    ],
    "surprise": [
        "Something caught you off guard? I love surprises too! "
        "How can I help you today?",
        "Oh, did I startle you? Sorry about that! "
        "Is there anything I can assist you with?",
    ],
    "happy": [
        "You look wonderful today! "
        "It's great to have you here. What can I help you find?",
        "Love the positive energy! "
        "Let's make this a great shopping trip — what are you looking for?",
        "Fantastic to see you smiling! "
        "How can I make your visit even better?",
    ],
    "neutral": [
        "Hello! Welcome. What can I help you with today?",
        "Hi there! Feel free to ask me anything about our products.",
        "Good to see you! How can I assist you today?",
    ],
}


# ---------------------------------------------------------------------------
# 2c. select_response()
#     Given an emotion string, return the chosen voice profile and a
#     randomly selected scripted line in one dict.
#
#     This is the single function that Part 3 (Pepper integration) will call
#     to know both *what* to say and *how* to say it.
# ---------------------------------------------------------------------------

def select_response(emotion: str) -> dict:
    """
    Pick a voice profile and a scripted response line for the given emotion.

    Parameters
    ----------
    emotion : str
        Dominant emotion returned by analyse_emotion(), e.g. "angry".

    Returns
    -------
    dict with keys:
        - emotion       (str)   the (possibly normalised) emotion label
        - text          (str)   the line Pepper should speak
        - pitch         (float) NAOqi pitchShift value
        - speed         (float) NAOqi speed multiplier (multiply by 100 for API)
        - description   (str)   human-readable label for the voice style
    """
    # Normalise to lowercase; fall back to neutral for any unknown label
    key = emotion.lower()
    if key not in VOICE_PROFILES:
        print(f"[EMOTION] Unknown emotion '{emotion}' — falling back to neutral.")
        key = "neutral"

    profile = VOICE_PROFILES[key]
    text    = random.choice(EMOTION_RESPONSES[key])

    print(f"[EMOTION] Voice profile : {profile['description']}")
    print(f"[EMOTION] Response text : \"{text}\"")

    return {
        "emotion":     key,
        "text":        text,
        "pitch":       profile["pitch"],
        "speed":       profile["speed"],
        "description": profile["description"],
    }


# ===========================================================================
# STANDALONE DEMO — run directly to test Parts 1 & 2 without Pepper hardware
# ===========================================================================

if __name__ == "__main__":
    import time

    print("=" * 50)
    print("  Emotion Detection — Part 1 + Part 2 Demo")
    print("=" * 50)
    print()
    print("Scanning your face every 4 seconds.")
    print("Press Ctrl-C to stop.")
    print()

    while True:
        result = detect_once(camera_index=0)
        if result:
            response = select_response(result["emotion"])
            print(f"  → Pepper would speak ({response['description']}):")
            print(f"    \"{response['text']}\"")
            print(f"    pitch={response['pitch']}  speed={response['speed']}")
        print()
        time.sleep(4)
