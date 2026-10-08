import sqlite3
import os
import time
from datetime import datetime
import cv2
import sys
import os
import re
from collections import Counter
import time
import csv
from ultralytics import YOLO
import easyocr
import numpy as np

# -----------------------------
# LOAD MODELS
# -----------------------------

model = YOLO("models/license_plate_detector.pt")
reader = easyocr.Reader(['en'])

# Create folder for saved detections
SAVE_FOLDER = "detected_vehicles"
os.makedirs(SAVE_FOLDER, exist_ok=True)

# Prevent duplicate saves
COOLDOWN = 10

plate_buffer = []
last_seen = {}
# Confirm plate before saving
plate_counts = {}
MIN_DETECTIONS = 3
plate_buffer = []
COOLDOWN = 10
# -----------------------------
# DATABASE
# -----------------------------
conn = sqlite3.connect(
    "vehicles.db"
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate TEXT,
    timestamp TEXT,
    source TEXT,
    image_path TEXT
)
""")

conn.commit()
plate_buffer = []
# -----------------------------
# CLEAN FUNCTION
# -----------------------------

def clean_plate(text):
    import re

    # Clean OCR text
    text = text.upper()
    text = text.replace("IND", "")
    text = text.replace(" ", "")
    text = re.sub(r"[^A-Z0-9]", "", text)

    if len(text) < 6:
        return text

    chars = list(text)

    # Safe OCR corrections
    digit_like = {
        "O": "0",
        "Q": "0",
        "D": "0",
        "I": "1",
        "L": "1",
        "Z": "2",
        "S": "5"
    }

    letter_like = {
        "0": "O",
        "1": "I",
        "2": "Z",
        "8": "B"
    }

    # -------- BH SERIES --------
    # Example: 22BH6517A
    bh_pattern = re.match(r"^\d{2}[A-Z]{2}", text)

    if bh_pattern:
        # First 2 must be digits
        for i in range(min(2, len(chars))):
            chars[i] = digit_like.get(chars[i], chars[i])

        # BH letters
        for i in range(2, min(4, len(chars))):
            chars[i] = letter_like.get(chars[i], chars[i])

        # Remaining characters untouched
        result = "".join(chars)

    # -------- NORMAL INDIAN --------
    # Example: RJ14CV0002
    else:
        # First 2 should be letters
        for i in range(min(2, len(chars))):
            chars[i] = letter_like.get(chars[i], chars[i])

        # Next 2 should be district digits
        for i in range(2, min(4, len(chars))):

            if chars[i] == "I":
                chars[i] = "1"

            elif chars[i] == "L":
                chars[i] = "4"

            elif chars[i] == "Z":
                # OCR often reads 4 as Z
                if i == 3:
                    chars[i] = "4"
                else:
                    chars[i] = "2"

            else:
                chars[i] = digit_like.get(chars[i], chars[i])        # Middle letters section
        middle_end = max(len(chars) - 4, 4)

        for i in range(4, middle_end):
            chars[i] = letter_like.get(chars[i], chars[i])

        # Last 4 should be digits
        for i in range(max(len(chars) - 4, 0), len(chars)):
            chars[i] = digit_like.get(chars[i], chars[i])

        result = "".join(chars)

    # Remove random long noisy outputs
    if len(result) > 10:
        result = result[:10]

    return result
# -----------------------------
# SAVE TO CSV
# -----------------------------
def save_to_csv(plate, source):
    file_exists = os.path.isfile("plates.csv")

    with open("plates.csv", "a", newline="") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(["PLATE", "SOURCE", "TIME"])

        writer.writerow([plate, source, time.strftime("%Y-%m-%d %H:%M:%S")])

# -----------------------------
# PROCESS SINGLE FRAME
# -----------------------------
def process_frame(frame, source="image"):
    results = model(frame)
    detected_plates = []

    for box in results[0].boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])

        pad = 10

        h, w = frame.shape[:2]

        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)

        plate = frame[y1:y2, x1:x2]

        cv2.imwrite("debug_plate.jpg", plate)

        if plate.size == 0:
            continue

        # Improve OCR
        gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)

        gray = cv2.resize(
            gray,
            None,
            fx=3,
            fy=3,
            interpolation=cv2.INTER_CUBIC
        )

        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        gray = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]

        text_list = reader.readtext(
            gray,
            detail=0,
            paragraph=False,
            decoder='beamsearch',
            width_ths=0.7,
            allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        )

        for text in text_list:
            raw_text = text.upper()

            junk = ["NUMBER", "PLATE", "VEHICLE", "CAR", "BOX"]
            if any(j in raw_text for j in junk):
                continue

            
            clean_text = clean_plate(raw_text)

            # Reject incomplete OCR
            if len(clean_text) < 8:
                continue

            # Validate Indian plate start
            if (
                len(clean_text) >= 2
                and not (
                    clean_text[:2].isalpha()
                    or clean_text[:2].isdigit()  # BH series
                )
            ):
                continue

            if 8 <= len(clean_text) <= 12:
                # Add to buffer
                plate_buffer.append(clean_text)

                # Keep last 10 readings
                if len(plate_buffer) > 10:
                    plate_buffer.pop(0)

                # Most common plate
                stable_plate = Counter(
                    plate_buffer
                ).most_common(1)[0][0]

                print("\nRAW:", raw_text)
                print("PLATE:", stable_plate)
                current_time = time.time()

                # Count detections
                if stable_plate not in plate_counts:
                    plate_counts[
                        stable_plate
                    ] = 1
                else:
                    plate_counts[
                        stable_plate
                    ] += 1

                # Save only after
                # 3 confirmations
                if (
                    plate_counts[
                        stable_plate
                    ] >= MIN_DETECTIONS
                ):

                    if (
                        stable_plate
                        not in last_seen
                        or current_time -
                        last_seen[
                            stable_plate
                        ]
                        > COOLDOWN
                    ):

                        last_seen[
                            stable_plate
                        ] = current_time

                        detected_plates.append(
                            stable_plate
                        )

                        save_to_csv(
                            stable_plate,
                            source
                        )

                        # Save image
                        timestamp = datetime.now(
                        ).strftime(
                            "%Y-%m-%d_%H-%M-%S"
                        )

                        filename = (
                            f"{stable_plate}_"
                            f"{timestamp}.jpg"
                        )

                        filepath = os.path.join(
                            SAVE_FOLDER,
                            filename
                        )

                        vehicle_crop = frame[
                            y1:y2,
                            x1:x2
                        ]

                        if vehicle_crop.size > 0:
                            cv2.imwrite(
                                filepath,
                                vehicle_crop
                            )

                        print(
                            f"SAVED: {filepath}"
                        )

                        # Save to database
                        timestamp_db = datetime.now(
                        ).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )

                        cursor.execute("""
                        INSERT INTO detections
                        (
                            plate,
                            timestamp,
                            source,
                            image_path
                        )
                        VALUES (?, ?, ?, ?)
                        """, (
                            stable_plate,
                            timestamp_db,
                            source,
                            filepath
                        ))

                        conn.commit()

                        print(
                            "Saved to database"
                        )
        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2
        )

        # Show stable plate on webcam
        if len(plate_buffer) > 0:

            stable_plate = Counter(
                plate_buffer
            ).most_common(1)[0][0]

            cv2.putText(
                frame,
                stable_plate,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

    return frame, detected_plates
# -----------------------------
# MODE 1: IMAGE
# -----------------------------
def run_image(path):
    image = cv2.imread(path)

    if image is None:
        print("Image not found:", path)
        return

    frame, plates = process_frame(image, path)

    cv2.imshow("ANPR - IMAGE", frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# -----------------------------
# MODE 2: FOLDER BATCH
# -----------------------------
def run_folder(folder):
    for file in os.listdir(folder):
        path = os.path.join(folder, file)

        if not path.lower().endswith((".jpg", ".png", ".jpeg")):
            continue

        print("\nProcessing:", path)
        image = cv2.imread(path)

        if image is None:
            continue

        frame, plates = process_frame(image, file)

        cv2.imshow("ANPR - BATCH", frame)
        cv2.waitKey(500)

    cv2.destroyAllWindows()

# -----------------------------
# MODE 3: WEBCAM (REAL TIME)
# -----------------------------
def run_webcam():
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        frame, plates = process_frame(frame, "webcam")

        cv2.imshow("ANPR - LIVE", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

# -----------------------------
# MAIN CONTROLLER
# -----------------------------
if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("""
Usage:
  python auto_anpr.py image.jpg
  python auto_anpr.py folder/
  python auto_anpr.py webcam
        """)
        exit()

    input_path = sys.argv[1]

    if input_path == "webcam":
        run_webcam()

    elif os.path.isdir(input_path):
        run_folder(input_path)

    else:
        run_image(input_path)
