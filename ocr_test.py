import easyocr

# Create OCR reader
reader = easyocr.Reader(['en'])

# Read text from image
result = reader.readtext('car.jpg')

# Print detected text
print(result)