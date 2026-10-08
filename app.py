from flask import Flask, render_template, send_from_directory, request, jsonify, session, redirect, url_for
import sqlite3
import os
import re
import csv
import threading
from datetime import datetime
from collections import Counter
import cv2
import numpy as np
from ultralytics import YOLO
import easyocr
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY') or os.urandom(32)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'vehicles.db')
SAVE_FOLDER = os.path.join(BASE_DIR, 'detected_vehicles')
os.makedirs(SAVE_FOLDER, exist_ok=True)

model = YOLO(os.path.join(BASE_DIR, 'models', 'license_plate_detector.pt'))
reader = easyocr.Reader(['en'])
inference_lock = threading.Lock()
last_logged_by_plate = {}
DETECTION_COOLDOWN_SECONDS = 15


def init_db():
    conn = sqlite3.connect(DB_PATH)
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT UNIQUE,
            registration_date TEXT,
            expiry_date TEXT,
            vehicle_type TEXT,
            status TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT
        )
    """)

    cursor.execute('SELECT COUNT(*) FROM vehicles')
    if cursor.fetchone()[0] == 0:
        demo_vehicles = [
            ('RJ14CV0002', '2022-01-15', '2027-01-15', 'Private Car', 'Active'),
            ('22BH6517A', '2024-03-10', '2029-03-10', 'Commercial Vehicle', 'Active'),
            ('KA01AB1234', '2021-06-05', '2026-06-05', 'Taxi', 'Expired'),
        ]
        cursor.executemany(
            'INSERT INTO vehicles (plate, registration_date, expiry_date, vehicle_type, status) VALUES (?, ?, ?, ?, ?)',
            demo_vehicles,
        )

    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            ('admin', generate_password_hash('admin123'), 'admin')
        )

    conn.commit()
    conn.close()


init_db()


def login_required(view):
    def wrapped(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return view(*args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


def get_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT plate, timestamp, source, image_path
        FROM detections
        ORDER BY id DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [
        (
            plate,
            timestamp,
            source,
            url_for('serve_vehicle_image', filename=os.path.basename(image_path)) if image_path else None,
        )
        for plate, timestamp, source, image_path in rows
    ]


def get_vehicles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, plate, registration_date, expiry_date, vehicle_type, status
        FROM vehicles
        ORDER BY plate ASC
    ''')
    data = cursor.fetchall()
    conn.close()
    return data


def clean_plate(text):
    text = text.upper().replace('IND', '').replace(' ', '')
    text = re.sub(r'[^A-Z0-9]', '', text)

    if len(text) < 6:
        return text

    chars = list(text)
    digit_like = {'O': '0', 'Q': '0', 'D': '0', 'I': '1', 'L': '1', 'Z': '2', 'S': '5'}
    letter_like = {'0': 'O', '1': 'I', '2': 'Z', '8': 'B'}

    if re.match(r'^\d{2}[A-Z]{2}', text):
        for i in range(min(2, len(chars))):
            chars[i] = digit_like.get(chars[i], chars[i])
        for i in range(2, min(4, len(chars))):
            chars[i] = letter_like.get(chars[i], chars[i])
        result = ''.join(chars)
    else:
        for i in range(min(2, len(chars))):
            chars[i] = letter_like.get(chars[i], chars[i])

        for i in range(2, min(4, len(chars))):
            if chars[i] == 'I':
                chars[i] = '1'
            elif chars[i] == 'L':
                chars[i] = '4'
            elif chars[i] == 'Z':
                if i == 3:
                    chars[i] = '4'
                else:
                    chars[i] = '2'
            else:
                chars[i] = digit_like.get(chars[i], chars[i])

        middle_end = max(len(chars) - 4, 4)
        for i in range(4, middle_end):
            chars[i] = letter_like.get(chars[i], chars[i])

        for i in range(max(len(chars) - 4, 0), len(chars)):
            chars[i] = digit_like.get(chars[i], chars[i])

        result = ''.join(chars)

    if len(result) > 10:
        result = result[:10]

    return result


def save_to_csv(plate, source):
    file_exists = os.path.isfile(os.path.join(BASE_DIR, 'plates.csv'))
    with open(os.path.join(BASE_DIR, 'plates.csv'), 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['PLATE', 'SOURCE', 'TIME'])
        writer.writerow([plate, source, datetime.now().strftime('%Y-%m-%d %H:%M:%S')])


def extract_plate_from_image(image):
    if image is None or image.size == 0:
        return None

    with inference_lock:
        results = model(image)
    candidates = []

    for box in results[0].boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        pad = 10
        h, w = image.shape[:2]
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)

        plate_region = image[y1:y2, x1:x2]
        if plate_region.size == 0:
            continue

        gray = cv2.cvtColor(plate_region, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        with inference_lock:
            text_list = reader.readtext(
                gray,
                detail=0,
                paragraph=False,
                decoder='beamsearch',
                width_ths=0.7,
                allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
            )

        for text in text_list:
            raw_text = text.upper()
            if any(j in raw_text for j in ['NUMBER', 'PLATE', 'VEHICLE', 'CAR', 'BOX']):
                continue

            clean_text = clean_plate(raw_text)
            if len(clean_text) < 8:
                continue

            if len(clean_text) >= 2 and not (clean_text[:2].isalpha() or clean_text[:2].isdigit()):
                continue

            if 8 <= len(clean_text) <= 12:
                candidates.append(clean_text)

    if not candidates:
        return None

    return Counter(candidates).most_common(1)[0][0]


def check_vehicle_registration(plate):
    plate = plate.strip().upper()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT plate, registration_date, expiry_date, vehicle_type, status FROM vehicles WHERE plate = ?',
        (plate,),
    )
    record = cursor.fetchone()
    conn.close()

    if not record:
        return {
            'status': 'not_registered',
            'message': f'Plate {plate} is not registered in the system.',
            'valid_until': None,
            'registration_date': None,
            'vehicle_type': None,
        }

    registration_date, expiry_date, vehicle_type, status = record[1], record[2], record[3], record[4]

    try:
        expiry = datetime.strptime(expiry_date, '%Y-%m-%d').date()
        today = datetime.now().date()
        if (status or '').lower() == 'blocked':
            result_status = 'blocked'
            message = f'Plate {plate} is registered but marked as blocked.'
        elif (status or '').lower() == 'expired' or today > expiry:
            result_status = 'expired'
            message = f'Plate {plate} is registered but the vehicle registration has expired.'
        else:
            result_status = 'registered'
            message = f'Plate {plate} is registered and valid.'
    except (TypeError, ValueError):
        result_status = status.lower() if status else 'registered'
        message = f'Plate {plate} is registered.'

    return {
        'status': result_status,
        'message': message,
        'valid_until': expiry_date,
        'registration_date': registration_date,
        'vehicle_type': vehicle_type,
    }


@app.route('/')
def home():
    data = get_data()
    return render_template('index.html', data=data)


@app.route('/live')
def live_monitor():
    return render_template('live.html')


@app.route('/history')
def detection_history():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, plate, timestamp, source, image_path
        FROM detections
        ORDER BY id DESC
        LIMIT 100
    ''')
    records = cursor.fetchall()
    conn.close()
    history = []
    for detection_id, plate, timestamp, source, image_path in records:
        status = check_vehicle_registration(plate)['status']
        image_url = url_for('serve_vehicle_image', filename=os.path.basename(image_path)) if image_path else None
        history.append((detection_id, plate, timestamp, source, image_url, status))
    return render_template('history.html', detections=history)


@app.route('/api/detections')
def recent_detections():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, plate, timestamp, source, image_path
        FROM detections
        ORDER BY id DESC
        LIMIT 10
    ''')
    records = cursor.fetchall()
    conn.close()
    detections = []
    for detection_id, plate, timestamp, source, image_path in records:
        result = check_vehicle_registration(plate)
        detections.append({
            'id': detection_id,
            'plate': plate,
            'timestamp': timestamp,
            'source': source,
            'status': result['status'],
            'image_url': url_for('serve_vehicle_image', filename=os.path.basename(image_path)) if image_path else None,
        })
    return jsonify(detections)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT username, password_hash FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session['admin_logged_in'] = True
            session['admin_user'] = username
            return redirect(url_for('admin_vehicles'))

        return render_template('admin_login.html', error='Invalid username or password.')

    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin/vehicles', methods=['GET', 'POST'])
@login_required
def admin_vehicles():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'delete':
            vehicle_id = request.form.get('vehicle_id')
            if vehicle_id:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM vehicles WHERE id = ?', (vehicle_id,))
                conn.commit()
                conn.close()
            return redirect(url_for('admin_vehicles'))

        if action == 'edit':
            vehicle_id = request.form.get('vehicle_id')
            plate = request.form.get('plate', '').strip().upper()
            registration_date = request.form.get('registration_date', '').strip()
            expiry_date = request.form.get('expiry_date', '').strip()
            vehicle_type = request.form.get('vehicle_type', '').strip()
            status = request.form.get('status', 'Active').strip()

            if vehicle_id and plate:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    UPDATE vehicles
                    SET plate = ?, registration_date = ?, expiry_date = ?, vehicle_type = ?, status = ?
                    WHERE id = ?
                    ''',
                    (plate, registration_date, expiry_date, vehicle_type, status, vehicle_id),
                )
                conn.commit()
                conn.close()
            return redirect(url_for('admin_vehicles'))

        plate = request.form.get('plate', '').strip().upper()
        registration_date = request.form.get('registration_date', '').strip()
        expiry_date = request.form.get('expiry_date', '').strip()
        vehicle_type = request.form.get('vehicle_type', '').strip()
        status = request.form.get('status', 'Active').strip()

        if plate:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO vehicles (plate, registration_date, expiry_date, vehicle_type, status) VALUES (?, ?, ?, ?, ?)',
                (plate, registration_date, expiry_date, vehicle_type, status),
            )
            conn.commit()
            conn.close()
        return redirect(url_for('admin_vehicles'))

    edit_id = request.args.get('edit', type=int)
    selected_vehicle = None
    if edit_id:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, plate, registration_date, expiry_date, vehicle_type, status FROM vehicles WHERE id = ?',
            (edit_id,),
        )
        selected_vehicle = cursor.fetchone()
        conn.close()

    data = get_vehicles()
    return render_template('admin_vehicles.html', vehicles=data, selected_vehicle=selected_vehicle)


@app.route('/detected_vehicles/<path:filename>')
def serve_vehicle_image(filename):
    return send_from_directory(SAVE_FOLDER, filename)


@app.route('/process_image', methods=['POST'])
def process_image():
    source = request.form.get('source', 'upload')

    if 'image' in request.files and request.files['image'].filename:
        file = request.files['image']
        image_bytes = file.read()
    else:
        data = request.get_data(cache=False)
        if not data:
            return jsonify({'error': 'No image data received.'}), 400
        image_bytes = data

    if len(image_bytes) > 10 * 1024 * 1024:
        return jsonify({'error': 'Image is too large. Please use an image under 10 MB.'}), 413

    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        return jsonify({'error': 'Unable to read the uploaded image.'}), 400

    plate = extract_plate_from_image(image)
    if not plate:
        return jsonify({
            'status': 'no_plate',
            'error': 'No valid number plate detected in the image.',
        })

    now = datetime.now()
    now_epoch = now.timestamp()
    should_log = (
        source != 'live-camera'
        or now_epoch - last_logged_by_plate.get(plate, 0) >= DETECTION_COOLDOWN_SECONDS
    )
    image_url = None

    if should_log:
        filename = f'{plate}_{now.strftime("%Y-%m-%d_%H-%M-%S_%f")}.jpg'
        filepath = os.path.join(SAVE_FOLDER, filename)
        if not cv2.imwrite(filepath, image):
            return jsonify({'error': 'Could not save the captured image.'}), 500

        save_to_csv(plate, source)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO detections (plate, timestamp, source, image_path) VALUES (?, ?, ?, ?)',
            (plate, now.strftime('%Y-%m-%d %H:%M:%S'), source, filepath),
        )
        conn.commit()
        conn.close()
        if source == 'live-camera':
            last_logged_by_plate[plate] = now_epoch
        image_url = url_for('serve_vehicle_image', filename=filename)

    result = check_vehicle_registration(plate)
    result['plate'] = plate
    result['image_url'] = image_url
    result['source'] = source
    result['logged'] = should_log
    result['timestamp'] = now.strftime('%Y-%m-%d %H:%M:%S')
    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')