# 🚗 ANPR System — Automatic Number Plate Recognition

### AI-Powered Vehicle License Plate Detection & OCR Pipeline

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge\&logo=python\&logoColor=white)](https://www.python.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-FF6600?style=for-the-badge)](https://ultralytics.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?style=for-the-badge\&logo=opencv\&logoColor=white)](https://opencv.org/)
[![EasyOCR](https://img.shields.io/badge/EasyOCR-Enabled-00C853?style=for-the-badge)](https://github.com/JaidedAI/EasyOCR)
[![PyTorch](https://img.shields.io/badge/PyTorch-Deep%20Learning-EE4C2C?style=for-the-badge\&logo=pytorch\&logoColor=white)](https://pytorch.org/)

A Computer Vision–based **Automatic Number Plate Recognition (ANPR)** system built using **YOLOv8, OpenCV, and EasyOCR** to detect and extract vehicle registration numbers from images and webcam input.

---

## 📌 Overview

This project detects vehicle number plates using a trained **YOLOv8 license plate detector** and extracts plate text using **EasyOCR**. It supports:

* 🖼️ Single image recognition
* 📁 Folder batch processing
* 🎥 Real-time webcam detection
* 📝 CSV logging of detected plates

The system also includes OCR text cleaning to improve number plate accuracy.

---

## ✨ Features

* 🚘 License plate detection using YOLOv8
* 🔍 OCR text extraction with EasyOCR
* 🧹 Automatic plate text cleaning & correction
* 🖼️ Single image processing
* 📁 Folder batch processing
* 🎥 Real-time webcam ANPR
* 📊 CSV logging of detected plates

---

## 🛠️ Tech Stack

| Technology         | Purpose                            |
| ------------------ | ---------------------------------- |
| Python             | Core programming language          |
| OpenCV             | Image processing & webcam handling |
| YOLO (Ultralytics) | License plate detection            |
| EasyOCR            | OCR text extraction                |
| PyTorch            | Deep learning backend              |

---

## 📂 Project Structure

```text
ANPR_project/
│── auto_anpr.py
│── detect_image.py
│── crop_plate.py
│── ocr_test.py
│── models/
│   └── license_plate_detector.pt
│── yolov8n.pt
│── car.jpg
│── plate.jpg
│── plates.csv
│── README.md
```

---

## ⚙️ Installation

### Clone the Repository

```bash
git clone https://github.com/noufeenfarah-eng/ANPR-System.git
cd ANPR-System
```

### Install Dependencies

```bash
pip install ultralytics opencv-python easyocr torch torchvision
```

---

## 🚀 Usage

### Run on Single Image

```bash
python auto_anpr.py car.jpg
```

### Run on Folder of Images

```bash
python auto_anpr.py folder/
```

### Run Real-Time Webcam Detection

```bash
python auto_anpr.py webcam
```

Press **Q** to quit webcam mode.

---

## 🌐 Web Dashboard

Install Flask in the same Python environment as the ANPR dependencies, then start the dashboard from the project folder:

```bash
pip install flask
python app.py
```

Open `http://127.0.0.1:5000` in a browser. The dashboard includes:

* **Dashboard** — upload one vehicle photo or process images from a selected folder.
* **Live Monitor** — choose a browser camera, start/stop continuous plate scanning, and select a scan interval.
* **History** — review the latest captured images and their current registration status.
* **Admin** — sign in to add, edit, or remove registry entries.

Camera access is available on `localhost` or an HTTPS site and requires browser permission. The web monitor sends sampled frames to the local ANPR server; model speed depends on the computer and available GPU.

For a new local demo database, the initial admin account is `admin` / `admin123`. The app uses a random secret key for local development; set the `FLASK_SECRET_KEY` environment variable to a securely generated value for a stable key, and change the demo credentials before exposing the application to other users or networks. Registry matches use the records in the local SQLite database; this project does not query an official government registry.

---

## 🧠 Working Pipeline

```text
Input Image / Webcam
        ↓
License Plate Detection (YOLOv8)
        ↓
Plate Cropping
        ↓
OCR Extraction (EasyOCR)
        ↓
Text Cleaning & Correction
        ↓
Detected Plate Output + CSV Logging
```

---

## 📊 Example Output

```text
RAW: KA G2MP 9657
CLEAN PLATE: KAG2MP9657
```

---

## 🌍 Real-World Applications

* 🚦 Traffic monitoring systems
* 🅿️ Smart parking access
* 🚔 Law enforcement & vehicle tracking
* 🏢 Secure vehicle entry systems
* 🛣️ Highway surveillance

---

## 🔮 Future Improvements

* Database integration (SQLite/MySQL)
* Blacklisted vehicle detection
* Better OCR accuracy for Indian plates
* Real-time dashboard UI
* Improved night-time detection

---

## 🎓 Learning Outcomes

Through this project, I gained hands-on experience in:

* Object Detection using YOLOv8
* OCR pipelines using EasyOCR
* OpenCV image processing
* Real-time computer vision systems
* AI model integration and post-processing

---

## 📄 License

This project is licensed under the MIT License.

---

⭐ If you found this project useful, consider giving it a star on GitHub!
