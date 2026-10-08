const video = document.getElementById('cameraPreview');
const cameraSelect = document.getElementById('cameraSelect');
const intervalSelect = document.getElementById('scanInterval');
const startButton = document.getElementById('startLiveBtn');
const stopButton = document.getElementById('stopLiveBtn');
const liveState = document.getElementById('liveState');
const liveDot = document.getElementById('liveDot');
const resultPanel = document.getElementById('liveResult');
const recentList = document.getElementById('liveRecent');
const scanCount = document.getElementById('scanCount');
const scanClock = document.getElementById('scanClock');
const placeholder = document.getElementById('videoPlaceholder');

let cameraStream = null;
let scanTimer = null;
let scanTotal = 0;
let scanning = false;
let requestInProgress = false;

function setLiveState(state, isLive) {
  liveState.textContent = state;
  liveDot.classList.toggle('is-live', isLive);
}

function showResult(data) {
  resultPanel.className = `result-box ${data.status || 'neutral'}`;
  const title = document.createElement('h3');
  const message = document.createElement('p');
  const details = document.createElement('p');

  const titles = {
    registered: 'Registered · Valid',
    expired: 'Registration expired',
    blocked: 'Vehicle blocked',
    not_registered: 'Not registered',
    no_plate: 'No plate in frame'
  };
  title.textContent = titles[data.status] || 'Plate detected';
  message.textContent = data.message || data.error || '';

  const info = data.plate ? [`Plate: ${data.plate}`] : [];
  if (data.vehicle_type) info.push(`Type: ${data.vehicle_type}`);
  if (data.valid_until) info.push(`Valid until: ${data.valid_until}`);
  details.textContent = info.join('  ·  ');

  resultPanel.replaceChildren(title, message, details);
}

async function refreshRecent() {
  try {
    const response = await fetch('/api/detections', { cache: 'no-store' });
    if (!response.ok) throw new Error(`Recent detections request failed (${response.status})`);
    const detections = await response.json();
    recentList.replaceChildren();

    if (!detections.length) {
      const empty = document.createElement('p');
      empty.className = 'empty-state';
      empty.textContent = 'No detections yet.';
      recentList.appendChild(empty);
      return;
    }

    for (const detection of detections.slice(0, 6)) {
      const item = document.createElement('div');
      item.className = 'recent-item';
      const plate = document.createElement('strong');
      plate.textContent = detection.plate;
      const meta = document.createElement('span');
      meta.textContent = `${detection.timestamp} · ${detection.status.replaceAll('_', ' ')}`;
      item.append(plate, meta);
      recentList.appendChild(item);
    }
  } catch (error) {
    setLiveState('Recent feed unavailable', scanning);
  }
}

async function scanFrame() {
  if (!scanning || !cameraStream || requestInProgress) return;
  requestInProgress = true;
  setLiveState('Scanning', true);

  try {
    const canvas = document.createElement('canvas');
    const maxWidth = 960;
    const scale = Math.min(1, maxWidth / (video.videoWidth || maxWidth));
    canvas.width = Math.round((video.videoWidth || 1280) * scale);
    canvas.height = Math.round((video.videoHeight || 720) * scale);
    const context = canvas.getContext('2d');
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    const imageBlob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.82));
    if (!imageBlob) throw new Error('The browser could not capture a camera frame.');

    const formData = new FormData();
    formData.append('image', imageBlob, 'live-frame.jpg');
    formData.append('source', 'live-camera');
    const response = await fetch('/process_image', { method: 'POST', body: formData });
    const result = await response.json();
    scanTotal += 1;
    scanCount.textContent = `${scanTotal} scans`;

    if (response.ok && result.status === 'no_plate') {
      setLiveState('Monitoring · no plate in frame', true);
      if (resultPanel.querySelector('h3')?.textContent === 'Waiting for camera') {
        showResult(result);
      }
    } else if (response.ok) {
      showResult(result);
      setLiveState(result.logged ? 'Plate recorded' : 'Monitoring', true);
      if (result.logged) {
        await refreshRecent();
      }
    } else {
      throw new Error(result.error || `Scan failed (${response.status})`);
    }
  } catch (error) {
    setLiveState(error.message || 'Scan error', false);
  } finally {
    requestInProgress = false;
    if (scanning) {
      scanTimer = window.setTimeout(scanFrame, Number(intervalSelect.value));
    }
  }
}

async function listCameras() {
  const devices = await navigator.mediaDevices.enumerateDevices();
  const cameras = devices.filter((device) => device.kind === 'videoinput');
  const selectedId = cameraSelect.value;
  cameraSelect.replaceChildren(new Option('Default camera', ''));
  cameras.forEach((camera, index) => {
    cameraSelect.add(new Option(camera.label || `Camera ${index + 1}`, camera.deviceId));
  });
  if (cameras.some((camera) => camera.deviceId === selectedId)) cameraSelect.value = selectedId;
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    setLiveState('Camera unavailable · use localhost or HTTPS', false);
    return;
  }

  try {
    if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop());
    const deviceId = cameraSelect.value;
    const videoConstraint = deviceId
      ? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
      : { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } };
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: videoConstraint, audio: false });
    video.srcObject = cameraStream;
    await video.play();
    placeholder.hidden = true;
    await listCameras();
    scanning = true;
    scanTotal = 0;
    scanCount.textContent = '0 scans';
    startButton.disabled = true;
    stopButton.disabled = false;
    setLiveState('Starting scan', true);
    scanFrame();
  } catch (error) {
    setLiveState(`Camera error: ${error.message}`, false);
  }
}

function stopCamera() {
  scanning = false;
  window.clearTimeout(scanTimer);
  if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  video.srcObject = null;
  placeholder.hidden = false;
  startButton.disabled = false;
  stopButton.disabled = true;
  setLiveState('Camera off', false);
}

startButton.addEventListener('click', startCamera);
stopButton.addEventListener('click', stopCamera);
cameraSelect.addEventListener('change', () => {
  if (scanning) startCamera();
});
intervalSelect.addEventListener('change', () => {
  if (!scanning) return;
  window.clearTimeout(scanTimer);
  scanTimer = window.setTimeout(scanFrame, Number(intervalSelect.value));
});
window.addEventListener('beforeunload', stopCamera);
window.setInterval(() => {
  scanClock.textContent = new Date().toLocaleTimeString();
}, 1000);

refreshRecent();
window.setInterval(refreshRecent, 10000);
