from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/predmet")
def subjects_list():
    return render_template("predmet.html")

@app.route("/predmet/<int:id>")
def subject_detail(id):
    return render_template("predmet_detalji.html", subject_id=id)

if __name__ == "__main__":
    app.run(debug=True)
