const uploadForm = document.getElementById('uploadForm');
const vehicleImageInput = document.getElementById('vehicleImage');
const vehicleFolderInput = document.getElementById('vehicleFolder');
const resultBox = document.getElementById('resultBox');
const batchProgress = document.getElementById('batchProgress');
const batchResults = document.getElementById('batchResults');
const startCameraBtn = document.getElementById('startCameraBtn');
const captureBtn = document.getElementById('captureBtn');
const cameraPreview = document.getElementById('cameraPreview');

let stream = null;

function setResult(status, title, details) {
  resultBox.className = `result-box ${status}`;
  resultBox.innerHTML = `
    <h3>${title}</h3>
    <p>${details}</p>
  `;
}

async function submitImage(file, source = 'upload') {
  if (!file) {
    setResult('neutral', 'No image selected', 'Please choose an image or use the camera first.');
    return null;
  }

  const formData = new FormData();
  formData.append('image', file);
  formData.append('source', source);

  try {
    const response = await fetch('/process_image', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
      setResult('danger', 'No valid plate detected', data.error || 'Unable to process the image.');
      return data;
    }

    if (data.status === 'no_plate') {
      setResult('neutral', 'No plate detected', data.error);
      return data;
    }

    const validUntil = data.valid_until ? `Valid until: ${data.valid_until}` : 'No valid registration record found';
    const vehicleType = data.vehicle_type ? `Vehicle type: ${data.vehicle_type}` : 'Vehicle type: N/A';

    if (data.status === 'registered') {
      setResult('success', `Vehicle Registered`, `${data.message}<br>Plate: ${data.plate}<br>${vehicleType}<br>${validUntil}`);
    } else if (data.status === 'expired') {
      setResult('warning', 'Registration Expired', `${data.message}<br>Plate: ${data.plate}<br>${vehicleType}<br>${validUntil}`);
    } else {
      setResult('danger', 'Not Registered', `${data.message}<br>Plate: ${data.plate}`);
    }

    if (data.image_url) {
      const existingImage = document.querySelector('.result-preview');
      if (existingImage) existingImage.remove();

      const preview = document.createElement('img');
      preview.className = 'result-preview';
      preview.src = data.image_url;
      preview.alt = 'Detected vehicle preview';
      resultBox.appendChild(preview);
    }
    return data;
  } catch (error) {
    setResult('danger', 'Processing failed', 'Could not process the image. Please try again.');
    return null;
  }
}

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = vehicleImageInput.files[0];
  await submitImage(file, 'upload');
});

vehicleFolderInput.addEventListener('change', async () => {
  const files = Array.from(vehicleFolderInput.files).filter((file) => file.type.startsWith('image/'));
  batchResults.replaceChildren();

  if (!files.length) {
    batchProgress.textContent = 'No supported images found in that folder.';
    return;
  }

  for (let index = 0; index < files.length; index += 1) {
    const file = files[index];
    batchProgress.textContent = `Processing photo ${index + 1} of ${files.length}: ${file.name}`;
    const result = await submitImage(file, 'folder');
    const item = document.createElement('div');
    item.className = `batch-result ${result?.status || 'no_plate'}`;
    const label = document.createElement('strong');
    label.textContent = file.webkitRelativePath || file.name;
    const status = document.createElement('span');
    status.textContent = result?.plate
      ? `${result.plate} · ${(result.status || 'detected').replaceAll('_', ' ')}`
      : result?.error || 'Could not process this photo.';
    item.append(label, status);
    batchResults.appendChild(item);
  }

  batchProgress.textContent = `Finished processing ${files.length} photo${files.length === 1 ? '' : 's'}.`;
  vehicleFolderInput.value = '';
});

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment' },
      audio: false
    });
    cameraPreview.srcObject = stream;
    setResult('neutral', 'Camera ready', 'Camera is active. Capture the vehicle image to verify the registration.');
  } catch (error) {
    setResult('danger', 'Camera access denied', 'Please allow camera access or upload a photo instead.');
  }
}

captureBtn.addEventListener('click', async () => {
  if (!stream) {
    setResult('neutral', 'Camera not started', 'Start the camera before capturing an image.');
    return;
  }

  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  canvas.width = cameraPreview.videoWidth || 1280;
  canvas.height = cameraPreview.videoHeight || 720;
  context.drawImage(cameraPreview, 0, 0, canvas.width, canvas.height);
  canvas.toBlob(async (blob) => {
    if (!blob) {
      setResult('danger', 'Capture failed', 'Unable to capture the camera image.');
      return;
    }
    await submitImage(blob, 'camera');
  }, 'image/jpeg', 0.9);
});

startCameraBtn.addEventListener('click', startCamera);
