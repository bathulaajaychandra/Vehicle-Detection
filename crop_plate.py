import cv2
import easyocr

# Load image
image = cv2.imread("car.jpg")

# Crop plate area manually
plate = image[466:567, 470:926]

# Save cropped plate image
cv2.imwrite("plate.jpg", plate)

# OCR reader
reader = easyocr.Reader(['en'])

# Read text from cropped plate
result = reader.readtext("plate.jpg")

# Print result
print(result)

# Show cropped plate
cv2.imshow("Plate", plate)

cv2.waitKey(0)
cv2.destroyAllWindows()