import sys
import os
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from bson import ObjectId

# Ensure parent directory is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import get_db, Config

def init_database(seed_demo_data=True):
    print("==================================================")
    print("      TEAMFINDER MONGODB INITIALIZATION")
    print("==================================================")
    print(f"Connecting to MongoDB at: {Config.MONGO_URI}")
    print(f"Database name: {Config.DB_NAME}")

    try:
        db = get_db()
        print("[OK] Connected to MongoDB server successfully.")
    except Exception as e:
        print(f"[FAIL] Could not connect to MongoDB: {e}")
        return False

    users_col = db["users"]
    profiles_col = db["student_profiles"]
    projects_col = db["projects"]
    requests_col = db["join_requests"]
    teams_col = db["team_members"]

    # 1. Create Indexes
    print("\nCreating indexes...")
    try:
        # Users indexes
        users_col.create_index("email", unique=True, name="idx_users_email_unique")
        print("  - [users] Created unique index on 'email'")

        # Student profiles indexes
        profiles_col.create_index("user_id", unique=True, name="idx_profiles_user_id_unique")
        profiles_col.create_index("skills", name="idx_profiles_skills")
        profiles_col.create_index("name", name="idx_profiles_name")
        print("  - [student_profiles] Created indexes on 'user_id' (unique), 'skills', 'name'")

        # Projects indexes
        projects_col.create_index("title", name="idx_projects_title")
        projects_col.create_index("skills_required", name="idx_projects_skills")
        projects_col.create_index("status", name="idx_projects_status")
        projects_col.create_index("owner_id", name="idx_projects_owner")
        projects_col.create_index("created_at", name="idx_projects_created_at")
        print("  - [projects] Created indexes on 'title', 'skills_required', 'status', 'owner_id', 'created_at'")

        # Join requests indexes
        # Compound unique index to prevent duplicate join requests for the same project
        requests_col.create_index(
            [("project_id", 1), ("student_id", 1)],
            unique=True,
            name="idx_requests_project_student_unique"
        )
        requests_col.create_index("project_id", name="idx_requests_project_id")
        requests_col.create_index("student_id", name="idx_requests_student_id")
        requests_col.create_index("status", name="idx_requests_status")
        print("  - [join_requests] Created compound unique index on (project_id, student_id)")

        # Team members indexes
        # Compound unique index to prevent duplicate team members
        teams_col.create_index(
            [("project_id", 1), ("user_id", 1)],
            unique=True,
            name="idx_teams_project_user_unique"
        )
        teams_col.create_index("project_id", name="idx_teams_project_id")
        teams_col.create_index("user_id", name="idx_teams_user_id")
        print("  - [team_members] Created compound unique index on (project_id, user_id)")

    except Exception as e:
        print(f"[WARNING] Error creating indexes: {e}")

    # 2. Create Default Administrator Account
    print("\nChecking Administrator account...")
    admin_email = "admin@teamfinder.edu"
    existing_admin = users_col.find_one({"email": admin_email})

    if not existing_admin:
        admin_id = ObjectId()
        admin_doc = {
            "_id": admin_id,
            "name": "System Administrator",
            "email": admin_email,
            "password_hash": generate_password_hash("AdminPassword123!"),
            "role": "admin",
            "created_at": datetime.now(timezone.utc),
            "is_active": True
        }
        users_col.insert_one(admin_doc)
        print(f"  - [OK] Default admin created: {admin_email} / AdminPassword123!")
    else:
        print(f"  - Admin account '{admin_email}' already exists.")

    # 3. Seed Demo Students and Projects if requested and empty
    if seed_demo_data:
        student_count = users_col.count_documents({"role": "student"})
        if student_count == 0:
            print("\nSeeding demo student profiles and collaborative projects...")
            demo_students = [
                {
                    "name": "Aarav Sharma",
                    "email": "aarav.sharma@college.edu",
                    "password": "Password123!",
                    "college": "College of Engineering & Technology",
                    "department": "Computer Science & Engineering",
                    "skills": ["Python", "Flask", "PostgreSQL", "Docker", "REST API"],
                    "interests": ["Full-Stack Development", "Cloud Computing", "Distributed Systems"],
                    "bio": "Passionate backend developer with experience in microservices and database design. Looking to build scalable web platforms."
                },
                {
                    "name": "Diya Patel",
                    "email": "diya.patel@college.edu",
                    "password": "Password123!",
                    "college": "College of Engineering & Technology",
                    "department": "Information Technology",
                    "skills": ["JavaScript", "React", "HTML5", "CSS3", "Bootstrap 5", "UI/UX"],
                    "interests": ["Frontend Engineering", "Design Systems", "Web Accessibility"],
                    "bio": "Creative frontend enthusiast who loves crafting modern, accessible user interfaces with Bootstrap and React."
                },
                {
                    "name": "Rohan Verma",
                    "email": "rohan.verma@college.edu",
                    "password": "Password123!",
                    "college": "College of Engineering & Technology",
                    "department": "Data Science & AI",
                    "skills": ["Python", "PyTorch", "Scikit-Learn", "FastAPI", "NLP"],
                    "interests": ["Artificial Intelligence", "Machine Learning", "Natural Language Processing"],
                    "bio": "Machine learning researcher interested in building intelligent conversational assistants and predictive modeling tools."
                },
                {
                    "name": "Ananya Iyer",
                    "email": "ananya.iyer@college.edu",
                    "password": "Password123!",
                    "college": "College of Engineering & Technology",
                    "department": "Computer Science & Engineering",
                    "skills": ["Java", "Spring Boot", "PostgreSQL", "Cybersecurity", "Python"],
                    "interests": ["Security Engineering", "FinTech", "Authentication Systems"],
                    "bio": "Security-first software developer keen on zero-trust architectures and secure web application development."
                },
                {
                    "name": "Kavya Reddy",
                    "email": "kavya.reddy@college.edu",
                    "password": "Password123!",
                    "college": "College of Engineering & Technology",
                    "department": "Electronics & Communication",
                    "skills": ["C++", "Embedded Systems", "IoT", "Python", "MQTT"],
                    "interests": ["Internet of Things", "Smart Campus", "Hardware Prototyping"],
                    "bio": "Hardware-software integration lover passionate about smart campus IoT devices and sensor networks."
                }
            ]

            created_students = []
            for s in demo_students:
                u_id = ObjectId()
                user_record = {
                    "_id": u_id,
                    "name": s["name"],
                    "email": s["email"],
                    "password_hash": generate_password_hash(s["password"]),
                    "role": "student",
                    "created_at": datetime.now(timezone.utc),
                    "is_active": True
                }
                users_col.insert_one(user_record)

                profile_record = {
                    "_id": ObjectId(),
                    "user_id": u_id,
                    "name": s["name"],
                    "email": s["email"],
                    "college": s["college"],
                    "department": s["department"],
                    "skills": s["skills"],
                    "interests": s["interests"],
                    "bio": s["bio"],
                    "updated_at": datetime.now(timezone.utc)
                }
                profiles_col.insert_one(profile_record)
                created_students.append((u_id, s))
                print(f"  - Created student: {s['name']} ({s['email']})")

            # Seed Projects
            p1_id = ObjectId()
            p1_doc = {
                "_id": p1_id,
                "title": "Smart Campus IoT Energy Monitoring System",
                "description": "An end-to-end IoT platform to monitor and optimize classroom electricity consumption using ESP32 sensor nodes, MQTT telemetry brokers, and a real-time analytics dashboard.",
                "owner_id": created_students[4][0], # Kavya
                "owner_name": created_students[4][1]["name"],
                "owner_email": created_students[4][1]["email"],
                "skills_required": ["IoT", "Python", "MQTT", "HTML5", "CSS3"],
                "team_size": 3,
                "status": "Open",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            projects_col.insert_one(p1_doc)
            # Add owner as team member
            teams_col.insert_one({
                "_id": ObjectId(),
                "project_id": p1_id,
                "user_id": created_students[4][0],
                "role": "Owner",
                "joined_at": datetime.now(timezone.utc)
            })

            p2_id = ObjectId()
            p2_doc = {
                "_id": p2_id,
                "title": "AI Study Buddy – Multilingual Academic Assistant",
                "description": "A web-based intelligent tutoring system leveraging NLP and generative models to summarize college lecture notes, generate flashcards, and test students with dynamic quizzes.",
                "owner_id": created_students[2][0], # Rohan
                "owner_name": created_students[2][1]["name"],
                "owner_email": created_students[2][1]["email"],
                "skills_required": ["Python", "NLP", "FastAPI", "React", "UI/UX"],
                "team_size": 4,
                "status": "Open",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            projects_col.insert_one(p2_doc)
            teams_col.insert_one({
                "_id": ObjectId(),
                "project_id": p2_id,
                "user_id": created_students[2][0],
                "role": "Owner",
                "joined_at": datetime.now(timezone.utc)
            })

            p3_id = ObjectId()
            p3_doc = {
                "_id": p3_id,
                "title": "Decentralized Peer-to-Peer Course Resource Exchange",
                "description": "A secure digital library for university students to share course notes, reference papers, and textbook summaries with tamper-proof verification and role-based access control.",
                "owner_id": created_students[0][0], # Aarav
                "owner_name": created_students[0][1]["name"],
                "owner_email": created_students[0][1]["email"],
                "skills_required": ["Python", "Flask", "PostgreSQL", "JavaScript", "Bootstrap 5"],
                "team_size": 3,
                "status": "Open",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            projects_col.insert_one(p3_doc)
            teams_col.insert_one({
                "_id": ObjectId(),
                "project_id": p3_id,
                "user_id": created_students[0][0],
                "role": "Owner",
                "joined_at": datetime.now(timezone.utc)
            })

            # Add Diya to Aarav's project as an accepted team member
            teams_col.insert_one({
                "_id": ObjectId(),
                "project_id": p3_id,
                "user_id": created_students[1][0], # Diya
                "role": "Member",
                "joined_at": datetime.now(timezone.utc)
            })
            requests_col.insert_one({
                "_id": ObjectId(),
                "project_id": p3_id,
                "student_id": created_students[1][0],
                "student_name": created_students[1][1]["name"],
                "student_email": created_students[1][1]["email"],
                "message": "Hi Aarav! I'd love to handle the frontend UI/UX and Bootstrap 5 views for this project.",
                "status": "Accepted",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            })

            # Add Rohan sending a pending request to Aarav's project
            requests_col.insert_one({
                "_id": ObjectId(),
                "project_id": p3_id,
                "student_id": created_students[2][0], # Rohan
                "student_name": created_students[2][1]["name"],
                "student_email": created_students[2][1]["email"],
                "message": "I can help with search indexing and NLP summarization of course notes!",
                "status": "Pending",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            })

            print("  - Created 3 initial projects, team memberships, and join requests.")
        else:
            print(f"  - Database already contains {student_count} student(s). Skipping sample data seed.")

    print("\n[SUCCESS] TeamFinder MongoDB database initialized successfully!")
    print("==================================================")
    return True

if __name__ == "__main__":
    init_database()
