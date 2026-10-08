from ultralytics import YOLO
import cv2

# Load AI model
model = YOLO("yolov8n.pt")

# Read image
image = cv2.imread("car.jpg")

# Detect objects
results = model(image)

# Draw boxes around detected objects
annotated_frame = results[0].plot()

# Show image
cv2.imshow("Car Detection", annotated_frame)

# Wait until key press
cv2.waitKey(0)

# Close window
cv2.destroyAllWindows()