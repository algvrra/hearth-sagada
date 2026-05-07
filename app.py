from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

DATA_FILE = "students.json"

def load_students():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_students(students):
    with open(DATA_FILE, "w") as f:
        json.dump(students, f, indent=2)

# ── Students ──────────────────────────────────────────────────────────────────

@app.route("/api/students", methods=["GET"])
def get_students():
    return jsonify(load_students())

@app.route("/api/students", methods=["POST"])
def add_student():
    students = load_students()
    data = request.get_json()

    name = data.get("name", "").strip()
    sr_code = data.get("sr_code", "").strip()
    program = data.get("program", "").strip()

    if not name or not sr_code or not program:
        return jsonify({"error": "Name, SR-Code, and Program are required."}), 400

    if any(s["sr_code"] == sr_code for s in students):
        return jsonify({"error": f"SR-Code '{sr_code}' already exists."}), 409

    student = {"name": name, "sr_code": sr_code, "program": program, "courses": []}
    students.append(student)
    save_students(students)
    return jsonify({"message": "Student added successfully.", "student": student}), 201

@app.route("/api/students/<sr_code>", methods=["GET"])
def get_student(sr_code):
    students = load_students()
    student = next((s for s in students if s["sr_code"] == sr_code), None)
    if not student:
        return jsonify({"error": "Student not found."}), 404
    return jsonify(student)

@app.route("/api/students/<sr_code>", methods=["PUT"])
def edit_student(sr_code):
    students = load_students()
    student = next((s for s in students if s["sr_code"] == sr_code), None)
    if not student:
        return jsonify({"error": "Student not found."}), 404

    data = request.get_json()
    student["name"] = data.get("name", student["name"]).strip()
    student["program"] = data.get("program", student["program"]).strip()

    save_students(students)
    return jsonify({"message": "Student updated.", "student": student})

@app.route("/api/students/<sr_code>", methods=["DELETE"])
def delete_student(sr_code):
    students = load_students()
    new_list = [s for s in students if s["sr_code"] != sr_code]
    if len(new_list) == len(students):
        return jsonify({"error": "Student not found."}), 404
    save_students(new_list)
    return jsonify({"message": "Student deleted."})

# ── Courses ───────────────────────────────────────────────────────────────────

@app.route("/api/students/<sr_code>/courses", methods=["POST"])
def add_courses(sr_code):
    students = load_students()
    student = next((s for s in students if s["sr_code"] == sr_code), None)
    if not student:
        return jsonify({"error": "Student not found."}), 404

    data = request.get_json()
    courses = data.get("courses", [])

    processed = []
    for c in courses:
        title = c.get("title", "").strip()
        try:
            grade = float(c.get("grade", 0))
        except (ValueError, TypeError):
            grade = 0.0
        if title:
            processed.append({"title": title, "grade": grade})

    student["courses"] = processed
    save_students(students)
    return jsonify({"message": "Courses saved.", "courses": processed})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
