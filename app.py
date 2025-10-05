import os
from flask import Flask, render_template, request, jsonify, url_for
from werkzeug.utils import secure_filename
from config import Config

# Inicijalizacija Flask aplikacije
app = Flask(__name__)
app.config.from_object(Config)

# -----------------------
# POMOĆNE FUNKCIJE
# -----------------------
def allowed_file(filename):
    """Proverava da li je ekstenzija fajla dozvoljena"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

def subject_folder(subject_id: int) -> str:
    """Kreira folder za predmet ako ne postoji"""
    folder = os.path.join(app.config["UPLOAD_FOLDER"], str(subject_id))
    os.makedirs(folder, exist_ok=True)
    return folder

# -----------------------
# RUTE ZA HTML STRANICE
# -----------------------
@app.route("/")
def index():
    """Početna (General Chat) stranica"""
    return render_template("index.html")

@app.route("/predmet")
def subjects_list():
    """Lista predmeta"""
    return render_template("predmet.html")

@app.route("/predmet/<int:id>")
def subject_detail(id):
    """Detalji o konkretnom predmetu"""
    return render_template("predmet_detalji.html", subject_id=id)

# -----------------------
# API RUTE ZA UPLOAD I PRIKAZ FAJLOVA
# -----------------------
@app.post("/api/predmet/<int:id>/upload")
def upload_documents(id):
    """Prima više fajlova za predmet (form field name: 'files')"""
    if "files" not in request.files:
        return jsonify({"ok": False, "error": "No files field provided"}), 400

    files = request.files.getlist("files")
    saved = []
    folder = subject_folder(id)

    for f in files:
        if f and allowed_file(f.filename):
            fname = secure_filename(f.filename)
            save_path = os.path.join(folder, fname)
            f.save(save_path)
            saved.append({
                "name": fname,
                "url": url_for("static", filename=f"predmet_documents/{id}/{fname}", _external=False)
            })

    return jsonify({"ok": True, "saved": saved, "count": len(saved)})

@app.get("/api/predmet/<int:id>/documents")
def list_documents(id):
    """Vraća listu fajlova za predmet"""
    folder = subject_folder(id)
    files = []

    for fname in sorted(os.listdir(folder)):
        full = os.path.join(folder, fname)
        if os.path.isfile(full):
            files.append({
                "name": fname,
                "url": url_for("static", filename=f"predmet_documents/{id}/{fname}", _external=False)
            })

    return jsonify({"ok": True, "files": files, "count": len(files)})

@app.delete("/api/predmet/<int:id>/documents/<path:filename>")
def delete_document(id, filename):
    """Brisanje dokumenta iz predmeta"""
    folder = subject_folder(id)
    file_path = os.path.join(folder, filename)

    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({"ok": True, "message": f"{filename} deleted"})
    else:
        return jsonify({"ok": False, "error": "File not found"}), 404

# -----------------------
# TESTNA RUTA
# -----------------------
@app.route("/health")
def health():
    """Provera da li app radi"""
    return jsonify(ok=True)

# -----------------------
# MAIN ENTRY POINT
# -----------------------
if __name__ == "__main__":
    print("Flask app pokrenuta na: http://127.0.0.1:5000")
    app.run(debug=True)
