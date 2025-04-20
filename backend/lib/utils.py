import uuid
import base64

def generate_query_id():
    return str(uuid.uuid4())

def generate_screenshot_base64(screenshot_path: str):
    with open(screenshot_path, "rb") as image_file:
        image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
    return image_base64
