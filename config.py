import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    # snimamo u: static/predmet_documents
    UPLOAD_FOLDER = os.path.join("static", "predmet_documents")
    # dozvoljene ekstenzije (možeš širiti po potrebi)
    ALLOWED_EXTENSIONS = {"pdf", "txt", "docx", "pptx", "md", "png", "jpg", "jpeg"}
