import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    UPLOAD_FOLDER = os.path.join("static", "predmet_documents")
    ALLOWED_EXTENSIONS = {"pdf", "txt", "docx", "pptx", "md", "png", "jpg", "jpeg"}

    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "study_buddy")
    USE_MONGO = os.getenv("USE_MONGO", "1") 