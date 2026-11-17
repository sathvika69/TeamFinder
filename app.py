import os
import re
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from bson.errors import InvalidId

from config import Config, get_db, get_collections

app = Flask(__name__)
app.config.from_object(Config)

# -------------------------------------------------------------
# HELPERS & SERIALIZERS
# -------------------------------------------------------------

def serialize_doc(doc):
    """Recursively converts MongoDB BSON types (ObjectId, datetime) to JSON serializable types."""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    if isinstance(doc, dict):
        new_doc = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                new_doc[k] = str(v)
            elif isinstance(v, datetime):
                new_doc[k] = v.isoformat()
            elif isinstance(v, dict):
                new_doc[k] = serialize_doc(v)
            elif isinstance(v, list):
                new_doc[k] = [serialize_doc(item) for item in v]
            else:
                new_doc[k] = v
        return new_doc
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc

def parse_object_id(id_str):
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        return None

def get_current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    uid = parse_object_id(session["user_id"])
    if not uid:
        return None
    user = db.users.find_one({"_id": uid})
    return user

@app.context_processor
def inject_user():
    """Injects current_user and current_profile into all Jinja templates."""
    user = get_current_user()
    profile = None
    if user and user.get("role") == "student":
        db = get_db()
        profile = db.student_profiles.find_one({"user_id": user["_id"]})
    return {
        "current_user": serialize_doc(user),
        "current_profile": serialize_doc(profile)
    }

# -------------------------------------------------------------
# AUTHENTICATION DECORATORS
# -------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required. Please log in."}), 401
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login_page", next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required."}), 401
            flash("Please log in as an administrator.", "warning")
            return redirect(url_for("login_page"))
        if session.get("role") != "admin":
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Admin privileges required."}), 403
            flash("Access denied. Administrator privileges required.", "danger")
            return redirect(url_for("dashboard_page"))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        if session.get("role") != "student":
            flash("This section is reserved for students.", "info")
            return redirect(url_for("admin_page"))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------------------------------------------
# FRONTEND TEMPLATE ROUTES
# -------------------------------------------------------------

@app.route("/")
def index():
    """Home / Landing page."""
    db = get_db()
    total_projects = db.projects.count_documents({})
    total_students = db.users.count_documents({"role": "student"})
    recent_projects = list(db.projects.find({"status": "Open"}).sort("created_at", -1).limit(6))
    return render_template(
        "index.html",
        total_projects=total_projects,
        total_students=total_students,
        recent_projects=serialize_doc(recent_projects)
    )

@app.route("/login")
def login_page():
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin_page"))
        return redirect(url_for("dashboard_page"))
    return render_template("login.html")

@app.route("/register")
def register_page():
    if "user_id" in session:
        return redirect(url_for("dashboard_page"))
    return render_template("register.html")

@app.route("/dashboard")
@login_required
def dashboard_page():
    if session.get("role") == "admin":
        return redirect(url_for("admin_page"))
    
    db = get_db()
    uid = parse_object_id(session["user_id"])
    
    # Platform metrics
    total_projects = db.projects.count_documents({})
    total_students = db.users.count_documents({"role": "student"})
    
    # Student specific metrics
    my_created_count = db.projects.count_documents({"owner_id": uid})
    my_joined_count = db.team_members.count_documents({"user_id": uid, "role": "Member"})
    
    # Pending requests received for my projects
    my_project_ids = [p["_id"] for p in db.projects.find({"owner_id": uid}, {"_id": 1})]
    pending_received_count = db.join_requests.count_documents({
        "project_id": {"$in": my_project_ids},
        "status": "Pending"
    })
    
    # Pending requests sent by me
    pending_sent_count = db.join_requests.count_documents({
        "student_id": uid,
        "status": "Pending"
    })

    # Recently created projects
    recent_projects = list(db.projects.find().sort("created_at", -1).limit(5))
    
    # My projects preview
    my_projects = list(db.projects.find({"owner_id": uid}).sort("created_at", -1).limit(4))

    return render_template(
        "dashboard.html",
        stats={
            "total_projects": total_projects,
            "total_students": total_students,
            "my_created_count": my_created_count,
            "my_joined_count": my_joined_count,
            "pending_received_count": pending_received_count,
            "pending_sent_count": pending_sent_count
        },
        recent_projects=serialize_doc(recent_projects),
        my_projects=serialize_doc(my_projects)
    )

@app.route("/profile")
@login_required
def profile_page():
    uid_str = request.args.get("user_id", session["user_id"])
    uid = parse_object_id(uid_str)
    if not uid:
        flash("Invalid user ID.", "danger")
        return redirect(url_for("dashboard_page"))
    
    db = get_db()
    user = db.users.find_one({"_id": uid})
    if not user:
        flash("Student profile not found.", "warning")
        return redirect(url_for("dashboard_page"))
    
    profile = db.student_profiles.find_one({"user_id": uid})
    
    # Fetch projects created by this student
    created_projects = list(db.projects.find({"owner_id": uid}))
    
    # Fetch projects this student has joined as a team member
    member_teams = list(db.team_members.find({"user_id": uid, "role": "Member"}))
    joined_project_ids = [t["project_id"] for t in member_teams]
    joined_projects = list(db.projects.find({"_id": {"$in": joined_project_ids}}))

    is_own_profile = (str(uid) == session["user_id"])

    return render_template(
        "profile.html",
        user_info=serialize_doc(user),
        profile=serialize_doc(profile),
        created_projects=serialize_doc(created_projects),
        joined_projects=serialize_doc(joined_projects),
        is_own_profile=is_own_profile
    )

@app.route("/projects")
@login_required
def projects_page():
    """Browse projects page with search and filter capabilities."""
    return render_template("projects.html")

@app.route("/projects/create")
@login_required
@student_required
def create_project_page():
    return render_template("create_project.html")

@app.route("/projects/<project_id>")
@login_required
def project_details_page(project_id):
    pid = parse_object_id(project_id)
    if not pid:
        flash("Invalid project ID.", "danger")
        return redirect(url_for("projects_page"))
    
    db = get_db()
    project = db.projects.find_one({"_id": pid})
    if not project:
        flash("Project not found.", "danger")
        return redirect(url_for("projects_page"))
    
    # Get team members
    team_records = list(db.team_members.find({"project_id": pid}))
    member_user_ids = [m["user_id"] for m in team_records]
    
    # Fetch member profile details
    profiles = {
        str(p["user_id"]): p for p in db.student_profiles.find({"user_id": {"$in": member_user_ids}})
    }
    users = {
        str(u["_id"]): u for u in db.users.find({"_id": {"$in": member_user_ids}}, {"password_hash": 0})
    }

    members_detail = []
    for m in team_records:
        uid_str = str(m["user_id"])
        user_data = users.get(uid_str, {})
        prof_data = profiles.get(uid_str, {})
        members_detail.append({
            "user_id": uid_str,
            "role": m.get("role", "Member"),
            "name": prof_data.get("name") or user_data.get("name", "Student"),
            "email": prof_data.get("email") or user_data.get("email", ""),
            "college": prof_data.get("college", ""),
            "department": prof_data.get("department", ""),
            "skills": prof_data.get("skills", []),
            "joined_at": m.get("joined_at")
        })

    # Current user's relationship with this project
    current_uid = parse_object_id(session["user_id"])
    is_owner = (str(project["owner_id"]) == session["user_id"])
    is_member = any(str(m["user_id"]) == session["user_id"] for m in team_records)
    
    user_request = None
    if not is_owner and not is_member:
        user_request = db.join_requests.find_one({"project_id": pid, "student_id": current_uid})

    current_count = len(team_records)
    max_capacity = project.get("team_size", 4)
    is_full = current_count >= max_capacity

    return render_template(
        "project_details.html",
        project=serialize_doc(project),
        members=serialize_doc(members_detail),
        current_count=current_count,
        max_capacity=max_capacity,
        is_full=is_full,
        is_owner=is_owner,
        is_member=is_member,
        user_request=serialize_doc(user_request)
    )

@app.route("/find-teammates")
@login_required
def find_teammates_page():
    return render_template("find_teammates.html")

@app.route("/requests")
@login_required
@student_required
def requests_page():
    return render_template("requests.html")

@app.route("/my-teams")
@login_required
@student_required
def my_teams_page():
    return render_template("my_teams.html")

@app.route("/admin")
@admin_required
def admin_page():
    return render_template("admin.html")

# -------------------------------------------------------------
# REST API ENDPOINTS: AUTHENTICATION
# -------------------------------------------------------------

@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.get_json() or request.form.to_dict()
    
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    confirm_password = data.get("confirm_password", "")
    college = data.get("college", "").strip()
    department = data.get("department", "").strip()
    skills_raw = data.get("skills", "")
    interests_raw = data.get("interests", "")
    bio = data.get("bio", "").strip()

    # Validation
    if not name or not email or not password:
        return jsonify({"success": False, "error": "Name, email and password are required."}), 400
    
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"success": False, "error": "Please provide a valid email address."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters long."}), 400

    if confirm_password and password != confirm_password:
        return jsonify({"success": False, "error": "Passwords do not match."}), 400

    # Parse skills and interests
    if isinstance(skills_raw, list):
        skills = [str(s).strip() for s in skills_raw if str(s).strip()]
    elif isinstance(skills_raw, str):
        skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
    else:
        skills = []

    if isinstance(interests_raw, list):
        interests = [str(i).strip() for i in interests_raw if str(i).strip()]
    elif isinstance(interests_raw, str):
        interests = [i.strip() for i in interests_raw.split(",") if i.strip()]
    else:
        interests = []

    db = get_db()
    # Check if email is already registered
    if db.users.find_one({"email": email}):
        return jsonify({"success": False, "error": "An account with this email already exists."}), 409

    # Strict rule: Role is ALWAYS 'student' on registration. Admin self-registration prohibited.
    user_id = ObjectId()
    now = datetime.now(timezone.utc)

    user_doc = {
        "_id": user_id,
        "name": name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "role": "student",
        "created_at": now,
        "is_active": True
    }
    db.users.insert_one(user_doc)

    profile_doc = {
        "_id": ObjectId(),
        "user_id": user_id,
        "name": name,
        "email": email,
        "college": college or "College of Engineering",
        "department": department or "Computer Science",
        "skills": skills,
        "interests": interests,
        "bio": bio,
        "updated_at": now
    }
    db.student_profiles.insert_one(profile_doc)

    # Automatically set session
    session["user_id"] = str(user_id)
    session["name"] = name
    session["email"] = email
    session["role"] = "student"

    return jsonify({
        "success": True,
        "message": "Registration successful! Welcome to TeamFinder.",
        "redirect_url": url_for("dashboard_page")
    }), 201

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json() or request.form.to_dict()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required."}), 400

    db = get_db()
    user = db.users.find_one({"email": email})

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"success": False, "error": "Invalid email or password."}), 401

    if not user.get("is_active", True):
        return jsonify({"success": False, "error": "Your account has been deactivated by the administrator."}), 403

    session["user_id"] = str(user["_id"])
    session["name"] = user["name"]
    session["email"] = user["email"]
    session["role"] = user.get("role", "student")

    redirect_url = url_for("admin_page") if user.get("role") == "admin" else url_for("dashboard_page")

    return jsonify({
        "success": True,
        "message": f"Welcome back, {user['name']}!",
        "role": user.get("role", "student"),
        "redirect_url": redirect_url
    }), 200

@app.route("/api/auth/logout", methods=["POST", "GET"])
def api_logout():
    session.clear()
    if request.is_json:
        return jsonify({"success": True, "message": "Logged out successfully."}), 200
    flash("You have been logged out.", "info")
    return redirect(url_for("login_page"))

@app.route("/api/auth/me", methods=["GET"])
def api_me():
    user = get_current_user()
    if not user:
        return jsonify({"authenticated": False, "user": None}), 200
    
    db = get_db()
    profile = db.student_profiles.find_one({"user_id": user["_id"]})
    return jsonify({
        "authenticated": True,
        "user": serialize_doc(user),
        "profile": serialize_doc(profile)
    }), 200

# -------------------------------------------------------------
# REST API ENDPOINTS: STUDENT PROFILES & DISCOVERY
# -------------------------------------------------------------

@app.route("/api/profiles/me", methods=["PUT"])
@login_required
def api_update_my_profile():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON payload provided."}), 400

    uid = parse_object_id(session["user_id"])
    db = get_db()

    name = data.get("name", "").strip()
    college = data.get("college", "").strip()
    department = data.get("department", "").strip()
    bio = data.get("bio", "").strip()
    skills = data.get("skills", [])
    interests = data.get("interests", [])

    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    if isinstance(interests, str):
        interests = [i.strip() for i in interests.split(",") if i.strip()]

    now = datetime.now(timezone.utc)

    # Update users collection name
    if name:
        db.users.update_one({"_id": uid}, {"$set": {"name": name}})
        session["name"] = name

    # Update or insert profile
    update_data = {
        "updated_at": now
    }
    if name: update_data["name"] = name
    if college: update_data["college"] = college
    if department: update_data["department"] = department
    if bio is not None: update_data["bio"] = bio
    if skills is not None: update_data["skills"] = skills
    if interests is not None: update_data["interests"] = interests

    db.student_profiles.update_one(
        {"user_id": uid},
        {"$set": update_data},
        upsert=True
    )

    updated_profile = db.student_profiles.find_one({"user_id": uid})
    return jsonify({
        "success": True,
        "message": "Profile updated successfully!",
        "profile": serialize_doc(updated_profile)
    }), 200

@app.route("/api/profiles/<user_id>", methods=["GET"])
@login_required
def api_get_profile(user_id):
    uid = parse_object_id(user_id)
    if not uid:
        return jsonify({"error": "Invalid user ID format."}), 400

    db = get_db()
    user = db.users.find_one({"_id": uid}, {"password_hash": 0})
    if not user:
        return jsonify({"error": "User not found."}), 404

    profile = db.student_profiles.find_one({"user_id": uid})
    return jsonify({
        "user": serialize_doc(user),
        "profile": serialize_doc(profile)
    }), 200

@app.route("/api/students", methods=["GET"])
@login_required
def api_search_students():
    """Teammate Discovery API with name query, department, and skill filters."""
    q = request.args.get("q", "").strip()
    skill_filter = request.args.get("skill", "").strip()

    db = get_db()
    query = {}

    if q:
        regex_q = re.compile(re.escape(q), re.IGNORECASE)
        query["$or"] = [
            {"name": regex_q},
            {"college": regex_q},
            {"department": regex_q},
            {"bio": regex_q}
        ]

    if skill_filter:
        regex_skill = re.compile(f"^{re.escape(skill_filter)}$", re.IGNORECASE)
        query["skills"] = regex_skill

    # Retrieve profiles
    profiles = list(db.student_profiles.find(query).sort("name", 1))

    # Also grab projects created count for each student
    results = []
    current_uid_str = session.get("user_id")

    for p in profiles:
        uid = p.get("user_id")
        created_count = db.projects.count_documents({"owner_id": uid})
        teams_count = db.team_members.count_documents({"user_id": uid})
        
        results.append({
            "profile": serialize_doc(p),
            "created_projects_count": created_count,
            "teams_count": teams_count,
            "is_me": (str(uid) == current_uid_str)
        })

    return jsonify({"students": results, "total": len(results)}), 200

# -------------------------------------------------------------
# REST API ENDPOINTS: PROJECT MANAGEMENT
# -------------------------------------------------------------

@app.route("/api/projects", methods=["GET"])
@login_required
def api_list_projects():
    """List projects with dynamic filtering and team size calculation."""
    db = get_db()
    q = request.args.get("q", "").strip()
    skill = request.args.get("skill", "").strip()
    status = request.args.get("status", "").strip()

    query = {}
    if q:
        regex_q = re.compile(re.escape(q), re.IGNORECASE)
        query["$or"] = [
            {"title": regex_q},
            {"description": regex_q},
            {"owner_name": regex_q}
        ]
    if skill:
        regex_skill = re.compile(f"^{re.escape(skill)}$", re.IGNORECASE)
        query["skills_required"] = regex_skill
    if status and status.lower() != "all":
        query["status"] = status

    projects = list(db.projects.find(query).sort("created_at", -1))
    
    # Enrich with current team member counts and user request status
    current_uid = parse_object_id(session["user_id"])
    enriched = []
    for p in projects:
        pid = p["_id"]
        member_count = db.team_members.count_documents({"project_id": pid})
        
        # Check current user's state on this project
        is_owner = (str(p.get("owner_id")) == session["user_id"])
        is_member = bool(db.team_members.find_one({"project_id": pid, "user_id": current_uid}))
        has_pending_request = bool(db.join_requests.find_one({
            "project_id": pid,
            "student_id": current_uid,
            "status": "Pending"
        }))

        doc = serialize_doc(p)
        doc["current_members"] = member_count
        doc["is_owner"] = is_owner
        doc["is_member"] = is_member
        doc["has_pending_request"] = has_pending_request
        doc["is_full"] = member_count >= p.get("team_size", 4)
        enriched.append(doc)

    return jsonify({"projects": enriched, "total": len(enriched)}), 200

@app.route("/api/projects", methods=["POST"])
@login_required
@student_required
def api_create_project():
    data = request.get_json() or request.form.to_dict()
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    team_size_val = data.get("team_size", 4)
    skills_raw = data.get("skills_required", [])
    status = data.get("status", "Open")

    if not title or not description:
        return jsonify({"success": False, "error": "Title and description are required."}), 400

    try:
        team_size = int(team_size_val)
        if team_size < 2 or team_size > 20:
            return jsonify({"success": False, "error": "Team size must be between 2 and 20."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid team size."}), 400

    if isinstance(skills_raw, str):
        skills_required = [s.strip() for s in skills_raw.split(",") if s.strip()]
    elif isinstance(skills_raw, list):
        skills_required = [str(s).strip() for s in skills_raw if str(s).strip()]
    else:
        skills_required = []

    if not skills_required:
        return jsonify({"success": False, "error": "At least one required skill is recommended."}), 400

    db = get_db()
    uid = parse_object_id(session["user_id"])
    now = datetime.now(timezone.utc)

    project_id = ObjectId()
    project_doc = {
        "_id": project_id,
        "title": title,
        "description": description,
        "owner_id": uid,
        "owner_name": session.get("name", "Student"),
        "owner_email": session.get("email", ""),
        "skills_required": skills_required,
        "team_size": team_size,
        "status": status if status in ["Open", "In Progress", "Completed"] else "Open",
        "created_at": now,
        "updated_at": now
    }
    db.projects.insert_one(project_doc)

    # Automatically add project owner as team leader / owner
    db.team_members.insert_one({
        "_id": ObjectId(),
        "project_id": project_id,
        "user_id": uid,
        "role": "Owner",
        "joined_at": now
    })

    return jsonify({
        "success": True,
        "message": "Project created successfully!",
        "project_id": str(project_id),
        "redirect_url": url_for("project_details_page", project_id=str(project_id))
    }), 201

@app.route("/api/projects/<project_id>", methods=["GET"])
@login_required
def api_get_project(project_id):
    pid = parse_object_id(project_id)
    if not pid:
        return jsonify({"error": "Invalid project ID."}), 400

    db = get_db()
    project = db.projects.find_one({"_id": pid})
    if not project:
        return jsonify({"error": "Project not found."}), 404

    # Fetch team members
    team_records = list(db.team_members.find({"project_id": pid}))
    member_user_ids = [m["user_id"] for m in team_records]
    
    profiles = {
        str(p["user_id"]): p for p in db.student_profiles.find({"user_id": {"$in": member_user_ids}})
    }

    members = []
    for m in team_records:
        uid_str = str(m["user_id"])
        prof = profiles.get(uid_str, {})
        members.append({
            "user_id": uid_str,
            "role": m.get("role", "Member"),
            "name": prof.get("name", "Student"),
            "email": prof.get("email", ""),
            "department": prof.get("department", ""),
            "skills": prof.get("skills", []),
            "joined_at": m.get("joined_at")
        })

    resp = serialize_doc(project)
    resp["members"] = serialize_doc(members)
    resp["current_members"] = len(team_records)
    resp["is_owner"] = (str(project["owner_id"]) == session["user_id"])
    return jsonify(resp), 200

@app.route("/api/projects/<project_id>", methods=["PUT"])
@login_required
def api_update_project(project_id):
    pid = parse_object_id(project_id)
    if not pid:
        return jsonify({"error": "Invalid project ID."}), 400

    db = get_db()
    project = db.projects.find_one({"_id": pid})
    if not project:
        return jsonify({"error": "Project not found."}), 404

    is_owner = (str(project["owner_id"]) == session["user_id"])
    is_admin = (session.get("role") == "admin")

    if not is_owner and not is_admin:
        return jsonify({"error": "Unauthorized. Only project owner or admin can edit this project."}), 403

    data = request.get_json() or {}
    update_fields = {"updated_at": datetime.now(timezone.utc)}

    if "title" in data and data["title"].strip():
        update_fields["title"] = data["title"].strip()
    if "description" in data and data["description"].strip():
        update_fields["description"] = data["description"].strip()
    if "status" in data and data["status"] in ["Open", "In Progress", "Completed"]:
        update_fields["status"] = data["status"]
    if "team_size" in data:
        try:
            ts = int(data["team_size"])
            current_members = db.team_members.count_documents({"project_id": pid})
            if ts < current_members:
                return jsonify({"error": f"Team size cannot be less than current member count ({current_members})."}), 400
            if ts < 2 or ts > 20:
                return jsonify({"error": "Team size must be between 2 and 20."}), 400
            update_fields["team_size"] = ts
        except ValueError:
            return jsonify({"error": "Invalid team size."}), 400
    if "skills_required" in data:
        skills = data["skills_required"]
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]
        update_fields["skills_required"] = skills

    db.projects.update_one({"_id": pid}, {"$set": update_fields})
    return jsonify({"success": True, "message": "Project updated successfully!"}), 200

@app.route("/api/projects/<project_id>", methods=["DELETE"])
@login_required
def api_delete_project(project_id):
    pid = parse_object_id(project_id)
    if not pid:
        return jsonify({"error": "Invalid project ID."}), 400

    db = get_db()
    project = db.projects.find_one({"_id": pid})
    if not project:
        return jsonify({"error": "Project not found."}), 404

    is_owner = (str(project["owner_id"]) == session["user_id"])
    is_admin = (session.get("role") == "admin")

    if not is_owner and not is_admin:
        return jsonify({"error": "Unauthorized. Only project owner or admin can delete this project."}), 403

    # Clean up associated join requests and team memberships
    db.join_requests.delete_many({"project_id": pid})
    db.team_members.delete_many({"project_id": pid})
    db.projects.delete_one({"_id": pid})

    return jsonify({"success": True, "message": "Project deleted successfully."}), 200

# -------------------------------------------------------------
# REST API ENDPOINTS: JOIN REQUESTS & TEAM FORMATION
# -------------------------------------------------------------

@app.route("/api/projects/<project_id>/request", methods=["POST"])
@login_required
@student_required
def api_send_join_request(project_id):
    pid = parse_object_id(project_id)
    if not pid:
        return jsonify({"success": False, "error": "Invalid project ID."}), 400

    db = get_db()
    project = db.projects.find_one({"_id": pid})
    if not project:
        return jsonify({"success": False, "error": "Project does not exist."}), 404

    uid = parse_object_id(session["user_id"])

    # Rule: Cannot join own project
    if str(project["owner_id"]) == session["user_id"]:
        return jsonify({"success": False, "error": "You are the owner of this project."}), 400

    # Rule: Project must be open
    if project.get("status") != "Open":
        return jsonify({"success": False, "error": f"Project is currently {project.get('status')}. Requests cannot be submitted."}), 400

    # Rule: Check team capacity
    current_members = db.team_members.count_documents({"project_id": pid})
    max_size = project.get("team_size", 4)
    if current_members >= max_size:
        return jsonify({"success": False, "error": "This team has already reached its maximum capacity."}), 400

    # Rule: Cannot join if already a member
    if db.team_members.find_one({"project_id": pid, "user_id": uid}):
        return jsonify({"success": False, "error": "You are already a member of this team."}), 400

    # Rule: Cannot send duplicate request
    existing_request = db.join_requests.find_one({"project_id": pid, "student_id": uid})
    if existing_request:
        status = existing_request.get("status", "Pending")
        return jsonify({
            "success": False,
            "error": f"You have already submitted a join request for this project (Status: {status})."
        }), 409

    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        message = "Hi! I am interested in collaborating on this project and contributing my skills."

    now = datetime.now(timezone.utc)
    request_doc = {
        "_id": ObjectId(),
        "project_id": pid,
        "project_title": project.get("title"),
        "project_owner_id": project.get("owner_id"),
        "student_id": uid,
        "student_name": session.get("name", "Student"),
        "student_email": session.get("email", ""),
        "message": message,
        "status": "Pending",
        "created_at": now,
        "updated_at": now
    }
    db.join_requests.insert_one(request_doc)

    return jsonify({
        "success": True,
        "message": "Join request sent successfully to the project owner!"
    }), 201

@app.route("/api/requests/received", methods=["GET"])
@login_required
@student_required
def api_get_received_requests():
    """Requests sent to projects owned by the logged-in student."""
    db = get_db()
    uid = parse_object_id(session["user_id"])

    # Find projects owned by user
    my_projects = list(db.projects.find({"owner_id": uid}))
    project_map = {p["_id"]: p for p in my_projects}
    project_ids = list(project_map.keys())

    requests = list(db.join_requests.find({"project_id": {"$in": project_ids}}).sort("created_at", -1))
    
    # Enrich with student profile info (skills, dept) and project title
    student_ids = [r["student_id"] for r in requests]
    profiles = {
        str(p["user_id"]): p for p in db.student_profiles.find({"user_id": {"$in": student_ids}})
    }

    enriched = []
    for r in requests:
        proj = project_map.get(r["project_id"], {})
        prof = profiles.get(str(r["student_id"]), {})
        current_members = db.team_members.count_documents({"project_id": r["project_id"]})
        max_size = proj.get("team_size", 4)

        rdoc = serialize_doc(r)
        rdoc["project_title"] = proj.get("title", "Project")
        rdoc["student_department"] = prof.get("department", "Student")
        rdoc["student_college"] = prof.get("college", "")
        rdoc["student_skills"] = prof.get("skills", [])
        rdoc["student_bio"] = prof.get("bio", "")
        rdoc["current_team_size"] = current_members
        rdoc["max_team_size"] = max_size
        rdoc["is_full"] = current_members >= max_size
        enriched.append(rdoc)

    return jsonify({"requests": enriched, "total": len(enriched)}), 200

@app.route("/api/requests/sent", methods=["GET"])
@login_required
@student_required
def api_get_sent_requests():
    """Requests sent by the logged-in student."""
    db = get_db()
    uid = parse_object_id(session["user_id"])

    requests = list(db.join_requests.find({"student_id": uid}).sort("created_at", -1))
    project_ids = [r["project_id"] for r in requests]
    projects = {p["_id"]: p for p in db.projects.find({"_id": {"$in": project_ids}})}

    enriched = []
    for r in requests:
        proj = projects.get(r["project_id"], {})
        rdoc = serialize_doc(r)
        rdoc["project_title"] = proj.get("title", "Deleted Project")
        rdoc["project_owner_name"] = proj.get("owner_name", "Owner")
        rdoc["project_status"] = proj.get("status", "Unknown")
        enriched.append(rdoc)

    return jsonify({"requests": enriched, "total": len(enriched)}), 200

@app.route("/api/requests/<request_id>/accept", methods=["POST"])
@login_required
@student_required
def api_accept_join_request(request_id):
    rid = parse_object_id(request_id)
    if not rid:
        return jsonify({"success": False, "error": "Invalid request ID."}), 400

    db = get_db()
    req = db.join_requests.find_one({"_id": rid})
    if not req:
        return jsonify({"success": False, "error": "Join request not found."}), 404

    pid = req["project_id"]
    project = db.projects.find_one({"_id": pid})
    if not project:
        return jsonify({"success": False, "error": "Project no longer exists."}), 404

    # Authorization: Only project owner can accept
    if str(project["owner_id"]) != session["user_id"]:
        return jsonify({"success": False, "error": "Only the project owner can accept join requests."}), 403

    if req.get("status") == "Accepted":
        return jsonify({"success": False, "error": "This request has already been accepted."}), 400

    # Rule: Prevent accepting beyond available team capacity
    current_members = db.team_members.count_documents({"project_id": pid})
    max_size = project.get("team_size", 4)
    if current_members >= max_size:
        return jsonify({
            "success": False,
            "error": f"Cannot accept request. Team is already at maximum capacity ({current_members}/{max_size})."
        }), 400

    now = datetime.now(timezone.utc)

    # Add member to team_members
    db.team_members.update_one(
        {"project_id": pid, "user_id": req["student_id"]},
        {"$setOnInsert": {
            "_id": ObjectId(),
            "project_id": pid,
            "user_id": req["student_id"],
            "role": "Member",
            "joined_at": now
        }},
        upsert=True
    )

    # Update request status
    db.join_requests.update_one(
        {"_id": rid},
        {"$set": {"status": "Accepted", "updated_at": now}}
    )

    # If team is now full, update project status to 'In Progress'
    new_count = current_members + 1
    if new_count >= max_size and project.get("status") == "Open":
        db.projects.update_one({"_id": pid}, {"$set": {"status": "In Progress"}})

    return jsonify({
        "success": True,
        "message": f"Join request accepted! {req.get('student_name')} has been added to the team.",
        "new_member_count": new_count
    }), 200

@app.route("/api/requests/<request_id>/reject", methods=["POST"])
@login_required
@student_required
def api_reject_join_request(request_id):
    rid = parse_object_id(request_id)
    if not rid:
        return jsonify({"success": False, "error": "Invalid request ID."}), 400

    db = get_db()
    req = db.join_requests.find_one({"_id": rid})
    if not req:
        return jsonify({"success": False, "error": "Join request not found."}), 404

    project = db.projects.find_one({"_id": req["project_id"]})
    if not project or str(project["owner_id"]) != session["user_id"]:
        return jsonify({"success": False, "error": "Only the project owner can reject requests."}), 403

    now = datetime.now(timezone.utc)
    db.join_requests.update_one(
        {"_id": rid},
        {"$set": {"status": "Rejected", "updated_at": now}}
    )

    return jsonify({"success": True, "message": "Join request rejected."}), 200

# -------------------------------------------------------------
# REST API ENDPOINTS: MY TEAMS
# -------------------------------------------------------------

@app.route("/api/my-teams", methods=["GET"])
@login_required
@student_required
def api_my_teams():
    """Retrieve all teams joined or created by the current student with full roster."""
    db = get_db()
    uid = parse_object_id(session["user_id"])

    # Find all team_members records for this user
    my_memberships = list(db.team_members.find({"user_id": uid}))
    project_ids = [m["project_id"] for m in my_memberships]

    projects = list(db.projects.find({"_id": {"$in": project_ids}}))
    teams_output = []

    for p in projects:
        pid = p["_id"]
        # All members of this team
        all_members = list(db.team_members.find({"project_id": pid}))
        member_uids = [m["user_id"] for m in all_members]

        profiles = {
            str(pr["user_id"]): pr for pr in db.student_profiles.find({"user_id": {"$in": member_uids}})
        }
        users = {
            str(u["_id"]): u for u in db.users.find({"_id": {"$in": member_uids}}, {"password_hash": 0})
        }

        roster = []
        for m in all_members:
            m_uid_str = str(m["user_id"])
            p_data = profiles.get(m_uid_str, {})
            u_data = users.get(m_uid_str, {})
            roster.append({
                "user_id": m_uid_str,
                "name": p_data.get("name") or u_data.get("name", "Student"),
                "email": p_data.get("email") or u_data.get("email", ""),
                "department": p_data.get("department", ""),
                "skills": p_data.get("skills", []),
                "role": m.get("role", "Member"),
                "joined_at": m.get("joined_at")
            })

        my_role = next((m.get("role") for m in all_members if str(m["user_id"]) == session["user_id"]), "Member")

        p_doc = serialize_doc(p)
        p_doc["my_role"] = my_role
        p_doc["roster"] = serialize_doc(roster)
        p_doc["member_count"] = len(roster)
        teams_output.append(p_doc)

    return jsonify({"teams": teams_output, "total": len(teams_output)}), 200

# -------------------------------------------------------------
# REST API ENDPOINTS: ADMIN MANAGEMENT
# -------------------------------------------------------------

@app.route("/api/admin/stats", methods=["GET"])
@admin_required
def api_admin_stats():
    db = get_db()
    total_users = db.users.count_documents({})
    total_students = db.users.count_documents({"role": "student"})
    total_admins = db.users.count_documents({"role": "admin"})
    total_projects = db.projects.count_documents({})
    open_projects = db.projects.count_documents({"status": "Open"})
    in_progress = db.projects.count_documents({"status": "In Progress"})
    completed = db.projects.count_documents({"status": "Completed"})
    total_requests = db.join_requests.count_documents({})
    total_teams = db.team_members.count_documents({})

    return jsonify({
        "total_users": total_users,
        "total_students": total_students,
        "total_admins": total_admins,
        "total_projects": total_projects,
        "open_projects": open_projects,
        "in_progress_projects": in_progress,
        "completed_projects": completed,
        "total_requests": total_requests,
        "total_teams": total_teams
    }), 200

@app.route("/api/admin/users", methods=["GET"])
@admin_required
def api_admin_users():
    db = get_db()
    users = list(db.users.find({}, {"password_hash": 0}).sort("created_at", -1))
    
    user_ids = [u["_id"] for u in users]
    profiles = {
        str(p["user_id"]): p for p in db.student_profiles.find({"user_id": {"$in": user_ids}})
    }

    enriched = []
    for u in users:
        uid_str = str(u["_id"])
        prof = profiles.get(uid_str, {})
        udoc = serialize_doc(u)
        udoc["college"] = prof.get("college", "-")
        udoc["department"] = prof.get("department", "-")
        udoc["skills"] = prof.get("skills", [])
        enriched.append(udoc)

    return jsonify({"users": enriched, "total": len(enriched)}), 200

@app.route("/api/admin/users/<user_id>/toggle-status", methods=["POST"])
@admin_required
def api_admin_toggle_user_status(user_id):
    uid = parse_object_id(user_id)
    if not uid:
        return jsonify({"success": False, "error": "Invalid user ID."}), 400

    if str(uid) == session["user_id"]:
        return jsonify({"success": False, "error": "Cannot deactivate your own administrator account."}), 400

    db = get_db()
    user = db.users.find_one({"_id": uid})
    if not user:
        return jsonify({"success": False, "error": "User not found."}), 404

    current_status = user.get("is_active", True)
    new_status = not current_status
    db.users.update_one({"_id": uid}, {"$set": {"is_active": new_status}})

    return jsonify({
        "success": True,
        "message": f"User '{user['name']}' has been {'activated' if new_status else 'deactivated'}.",
        "is_active": new_status
    }), 200

@app.route("/api/admin/users/<user_id>", methods=["DELETE"])
@admin_required
def api_admin_delete_user(user_id):
    uid = parse_object_id(user_id)
    if not uid:
        return jsonify({"success": False, "error": "Invalid user ID."}), 400

    if str(uid) == session["user_id"]:
        return jsonify({"success": False, "error": "Cannot delete your own admin account."}), 400

    db = get_db()
    # Clean up user's projects, memberships, requests, and profile
    db.projects.delete_many({"owner_id": uid})
    db.team_members.delete_many({"user_id": uid})
    db.join_requests.delete_many({"student_id": uid})
    db.student_profiles.delete_one({"user_id": uid})
    db.users.delete_one({"_id": uid})

    return jsonify({"success": True, "message": "User and associated records removed successfully."}), 200

@app.route("/api/admin/projects", methods=["GET"])
@admin_required
def api_admin_projects():
    db = get_db()
    projects = list(db.projects.find().sort("created_at", -1))
    
    enriched = []
    for p in projects:
        pid = p["_id"]
        members_count = db.team_members.count_documents({"project_id": pid})
        requests_count = db.join_requests.count_documents({"project_id": pid})
        doc = serialize_doc(p)
        doc["members_count"] = members_count
        doc["requests_count"] = requests_count
        enriched.append(doc)

    return jsonify({"projects": enriched, "total": len(enriched)}), 200

# -------------------------------------------------------------
# RUNNER
# -------------------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG
    )
