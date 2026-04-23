# emotion_detection.py
# 1 — Core Detection Engine  (camera capture + DeepFace analysis)
# 2 — Voice & Response Logic (voice profiles + scripted responses)
# 3 — Pepper Integration     (EmotionDetector class, cooldown, background thread)
#
# Dependencies:
#   pip install opencv-python deepface tf-keras
#
# Run standalone demo (no Pepper hardware needed):
#   python emotion_detection.py

import cv2
import time
import random
import threading
import json
import os
from deepface import DeepFace

# Load emotion responses and voice profiles from JSON
try:
    _dir = os.path.dirname(os.path.abspath(__file__))
    _json_path = os.path.join(_dir, "responses.json")
    with open(_json_path, "r", encoding="utf-8") as _f:
        EMOTION_DATA = json.load(_f)
except FileNotFoundError:
    print("[EMOTION] ERROR: responses.json not found! Falling back to empty defaults.")
    EMOTION_DATA = {}


# ===========================================================================
# 1 — CORE DETECTION ENGINE
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

    print(f"[EMOTION] Frame captured — shape: {frame.shape}")
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

    Used internally by the EmotionDetector class in Part 3.
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
# 2 — VOICE & RESPONSE LOGIC
# ===========================================================================

# ---------------------------------------------------------------------------
# 2a. VOICE PROFILES AND RESPONSES (Now imported from responses.json)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 2b. select_response()
#     Given an emotion string, return the chosen voice profile and a
#     randomly selected scripted line in one dict.
#
#     This is the single function that Part 3 (Pepper integration) calls
#     to know both *what* to say and *how* to say it.
# ---------------------------------------------------------------------------

def select_response(emotion: str) -> dict:
    """
    Pick a voice profile and a scripted response line for the given emotion
    from the loaded JSON configuration.

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
    if key not in EMOTION_DATA:
        print(f"[EMOTION] Unknown emotion '{emotion}' — falling back to neutral.")
        key = "neutral"

    # Fallback to defaults if 'neutral' is missing or JSON didn't load
    if key not in EMOTION_DATA:
        return {"emotion": key, "text": "Hello.", "pitch": 1.0, "speed": 1.0, "description": "default fallback"}

    data = EMOTION_DATA[key]
    
    # Pick a random phrase from the 'responses' array
    phrase_list = data.get("responses", ["Hello."])
    text = random.choice(phrase_list)

    description = data.get("description", "friendly and natural")
    pitch = data.get("pitch", 1.0)
    speed = data.get("speed", 1.0)

    print(f"[EMOTION] Voice profile : {description}")
    print(f"[EMOTION] Response text : \"{text}\"")

    return {
        "emotion":     key,
        "text":        text,
        "pitch":       pitch,
        "speed":       speed,
        "description": description,
    }


# ===========================================================================
# 3 — PEPPER INTEGRATION & CONTINUOUS MODE
# ===========================================================================

# ---------------------------------------------------------------------------
# 3. EmotionDetector CLASS
#
#    Wraps Parts 1 and 2 and adds:
#      - Direct connection to PepperRobot (from pepper_api.py)
#      - Cooldown timer  → Pepper won't respond more often than every N seconds
#      - Background thread via run_continuous() → runs silently alongside
#        the orchestrator's LLM conversation loop
#      - Graceful stop() to end the background thread cleanly
#
#    Usage in orchestrator.py:
#        from emotion_detection import EmotionDetector
#        detector = EmotionDetector(pepper, cooldown_seconds=15)
#        detector.run_continuous(interval_seconds=2.0)
# ---------------------------------------------------------------------------

class EmotionDetector:
    """
    Continuously detects customer facial emotions via the webcam and
    instructs Pepper to respond with an appropriate voice tone and message.

    Parameters
    ----------
    pepper : PepperRobot
        An instance of PepperRobot from pepper_api.py.
        Must have a .say(text) method.
    camera_index : int
        OpenCV camera index (0 = built-in / first USB webcam).
    cooldown_seconds : int
        Minimum gap in seconds between consecutive Pepper responses.
        Prevents Pepper from interrupting a customer repeatedly.
    """

    def __init__(self, pepper, camera_index: int = 0, cooldown_seconds: int = 10):
        self.pepper           = pepper
        self.camera_index     = camera_index
        self.cooldown_seconds = cooldown_seconds

        self._last_response_time = 0.0   # unix timestamp of last Pepper response
        self._running            = False  # flag that controls the background loop
        self._lock               = threading.Lock()  # thread-safe flag access

        print(
            f"[EMOTION] EmotionDetector ready "
            f"(camera={camera_index}, cooldown={cooldown_seconds}s)"
        )

    # ------------------------------------------------------------------
    # 3a. PUBLIC API
    # ------------------------------------------------------------------

    def run_once(self) -> dict | None:
        """
        Capture one frame, detect emotion, and make Pepper respond.

        Call this when you want a single on-demand scan — e.g. triggered
        by a motion sensor or a specific node in the Node-RED flow.

        Returns
        -------
        dict  { emotion, confidence, face_count } from detect_once()
        or None if the camera or face detection failed.
        """
        result = detect_once(self.camera_index)
        if result is None:
            return None

        self._respond(result["emotion"], result["confidence"])
        return result

    def run_continuous(self, interval_seconds: float = 1.5) -> threading.Thread:
        """
        Start a background thread that calls run_once() repeatedly.

        Returns immediately — the rest of your program keeps running.
        Call stop() to end the thread gracefully.

        Parameters
        ----------
        interval_seconds : float
            Seconds to wait between each frame grab.
        """
        with self._lock:
            if self._running:
                print("[EMOTION] Already running in continuous mode.")
                return

            self._running = True

        print(
            f"[EMOTION] Continuous mode started "
            f"(interval={interval_seconds}s, cooldown={self.cooldown_seconds}s). "
            f"Call stop() to end."
        )

        thread = threading.Thread(
            target=self._loop,
            args=(interval_seconds,),
            daemon=True,   # thread exits automatically when the main program exits
        )
        thread.start()
        return thread

    def stop(self):
        """Signal the background loop to stop after the current cycle."""
        with self._lock:
            self._running = False
        print("[EMOTION] Stop signal sent — loop will end after current cycle.")

    # ------------------------------------------------------------------
    # 3b. INTERNAL — PEPPER RESPONSE
    # ------------------------------------------------------------------

    def _respond(self, emotion: str, confidence: float):
        """
        Apply the correct voice + scripted line and make Pepper speak.

        Enforces the cooldown period — if Pepper spoke recently this call
        is silently skipped so the customer is not interrupted mid-sentence.

        Parameters
        ----------
        emotion : str
            Dominant emotion string from DeepFace.
        confidence : float
            0–100 confidence percentage (informational only here).
        """
        now = time.time()
        elapsed = now - self._last_response_time

        if elapsed < self.cooldown_seconds:
            remaining = self.cooldown_seconds - elapsed
            print(f"[EMOTION] Cooldown — {remaining:.1f}s remaining. Skipping response.")
            return

        # Select the right text and voice settings (from Part 2)
        response = select_response(emotion)

        # ------------------------------------------------------------------
        # Apply NAOqi voice parameters on real Pepper hardware.
        # The pypepper wrapper does not yet expose ALTextToSpeech directly,
        # so the pitch/speed values are logged here for reference.
        # When connected to NAOqi you would call:
        #     tts = session.service("ALTextToSpeech")
        #     tts.setParameter("pitchShift", response["pitch"])
        #     tts.setParameter("speed",      response["speed"] * 100)
        # ------------------------------------------------------------------
        print(
            f"[EMOTION] Applying voice: "
            f"pitch={response['pitch']}  speed={response['speed']}"
        )

        # Tell Pepper to speak — uses PepperRobot.say() from pepper_api.py
        self.pepper.say(response["text"])

        self._last_response_time = time.time()

    # ------------------------------------------------------------------
    # 3c. INTERNAL — BACKGROUND LOOP
    # ------------------------------------------------------------------

    def _loop(self, interval_seconds: float):
        """Background thread body — runs until stop() is called."""
        while True:
            with self._lock:
                if not self._running:
                    break

            self.run_once()
            time.sleep(interval_seconds)

        print("[EMOTION] Background loop stopped.")


# ===========================================================================
# STANDALONE DEMO
# Run:  python emotion_detection.py
# Uses MockPepper so no Pepper hardware is needed.
# ===========================================================================

if __name__ == "__main__":

    class MockPepper:
        """Simulates PepperRobot.say() by printing to the console."""
        def say(self, text, language="english"):
            print(f"  ╔══ PEPPER SPEAKS ({language})")
            print(f"  ║   {text}")
            print(f"  ╚══")

    print("=" * 55)
    print("  Emotion Detection — Full Demo (Parts 1 + 2 + 3)")
    print("=" * 55)
    print()
    print("  • Webcam scans every 2 seconds")
    print("  • Pepper responds at most every 8 seconds (cooldown)")
    print("  • Press Ctrl-C to stop")
    print()

    detector = EmotionDetector(
        pepper=MockPepper(),
        camera_index=0,
        cooldown_seconds=8,
    )

    thread = detector.run_continuous(interval_seconds=2.0)

    try:
        # Keep the main thread alive so the daemon thread keeps running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        detector.stop()
        print("\n  Demo ended. Goodbye!")
