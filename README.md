# TEAMFINDER – Full-Stack Student Collaboration Platform
**SESD (Software Engineering & System Development) College Project**

TeamFinder is a full-stack web application designed for university and college campuses to help students discover teammates for academic projects, capstone assignments, and hackathons based on technical skills, project requirements, and academic interests.

---

## 🚀 Key Features

1. **Role-Based Authentication & Security**:
   - Secure student registration and session-based authentication.
   - Password hashing with Werkzeug (`scrypt`).
   - Role separation between Students and Administrators.
   - Safeguard preventing students from self-assigning administrator privileges.

2. **Student Profile Management**:
   - Comprehensive profile containing Name, Email, College, Department, Bio.
   - Array-based storage for technical skills and interests in MongoDB.
   - Interactive profile editing and public student profile exploration.

3. **Collaborative Project Management**:
   - Create, edit, and delete academic projects.
   - Specify prerequisites, required skills, and team capacity limits (2–20 members).
   - Dynamic project statuses (`Open`, `In Progress`, `Completed`).
   - Automatic team leader assignment upon project creation.

4. **Teammate Discovery**:
   - Filter students by technical competencies (e.g. Python, React, Flask, NLP, IoT).
   - Real-time search across names, departments, and college affiliations.

5. **Join Request Workflow & Capacity Enforcement**:
   - Students can submit join requests with custom introductory pitches.
   - Compound unique index in MongoDB prevents duplicate requests.
   - Project creators can review applicant profiles and accept/reject requests.
   - **Strict Capacity Guard**: The system prevents accepting join requests once team capacity is reached.

6. **My Teams Hub**:
   - Unified workspace displaying all teams created or joined by the student.
   - Displays teammate contact details, roles (`Owner` / `Member`), and technical skill tags.

7. **Administrator Control Console**:
   - Real-time platform metrics (Users, Students, Projects by status, Requests, Teams).
   - User account activation / deactivation and cascade account deletion.
   - Project moderation: review and remove inappropriate project listings.

---

## 🛠️ Technology Stack

- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3, Bootstrap Icons
- **Backend**: Python 3.13, Flask 3.0.3, RESTful JSON APIs
- **Database**: MongoDB Community Server 8.2 (Local: `mongodb://127.0.0.1:27017/`)
- **Database Driver**: PyMongo 4.19.0
- **Configuration**: Python-dotenv (`.env`)

---

## 📂 Project Directory Structure

```text
TeamFinder/
├── .env                    # Environment configuration
├── .gitignore              # Git ignore file
├── app.py                  # Main Flask application & REST APIs
├── config.py               # MongoDB connection & configuration
├── requirements.txt        # Python dependencies
├── README.md               # Project documentation
├── database/
│   └── init_db.py          # MongoDB collections, indexes, & seed script
├── static/
│   ├── css/
│   │   └── style.css       # Custom modern UI styling
│   └── js/
│       └── main.js         # Client-side scripts & toast notifications
└── templates/
    ├── base.html           # Master layout with navbar & footer
    ├── index.html          # Landing / Home page
    ├── login.html          # Student & Admin login page
    ├── register.html       # Student registration page
    ├── dashboard.html      # Student dashboard with live statistics
    ├── profile.html        # Profile management & edit modal
    ├── projects.html       # Browse projects with filters & search
    ├── create_project.html # Post project idea form
    ├── find_teammates.html # Teammate discovery page
    ├── project_details.html# Project details, roster, & join modal
    ├── requests.html       # Received & Sent join requests
    ├── my_teams.html       # Joined & Owned teams roster view
    └── admin.html          # Administrator console
```

---

## 🗄️ MongoDB Collections & Schema

The application uses the `TeamFinder` database on `mongodb://127.0.0.1:27017/`:

1. `users`:
   - `_id`: `ObjectId`
   - `name`: `string`
   - `email`: `string` (Unique index)
   - `password_hash`: `string` (Werkzeug hash)
   - `role`: `'student'` or `'admin'`
   - `created_at`: `datetime` (UTC)
   - `is_active`: `boolean`

2. `student_profiles`:
   - `_id`: `ObjectId`
   - `user_id`: `ObjectId` (Unique index referencing `users._id`)
   - `name`: `string`
   - `email`: `string`
   - `college`: `string`
   - `department`: `string`
   - `skills`: `array` of `string` (Indexed for search)
   - `interests`: `array` of `string`
   - `bio`: `string`
   - `updated_at`: `datetime` (UTC)

3. `projects`:
   - `_id`: `ObjectId`
   - `title`: `string` (Indexed)
   - `description`: `string`
   - `owner_id`: `ObjectId` (Indexed referencing `users._id`)
   - `owner_name`: `string`
   - `owner_email`: `string`
   - `skills_required`: `array` of `string` (Indexed)
   - `team_size`: `integer` (Total capacity, min 2)
   - `status`: `'Open'`, `'In Progress'`, or `'Completed'` (Indexed)
   - `created_at`, `updated_at`: `datetime` (UTC)

4. `join_requests`:
   - `_id`: `ObjectId`
   - `project_id`: `ObjectId`
   - `student_id`: `ObjectId`
   - `student_name`: `string`
   - `student_email`: `string`
   - `message`: `string`
   - `status`: `'Pending'`, `'Accepted'`, `'Rejected'`
   - **Compound Unique Index**: `(project_id, student_id)` to prevent duplicate join requests.

5. `team_members`:
   - `_id`: `ObjectId`
   - `project_id`: `ObjectId`
   - `user_id`: `ObjectId`
   - `role`: `'Owner'` or `'Member'`
   - `joined_at`: `datetime` (UTC)
   - **Compound Unique Index**: `(project_id, user_id)` to prevent duplicate memberships.

---

## ⚡ Quick Start Guide (Windows)

### 1. Prerequisites
- **Python 3.10+** (Python 3.13 tested)
- **MongoDB Community Server** installed and running on port `27017`.

### 2. Install Dependencies
Open PowerShell or Command Prompt in the `TeamFinder` folder:

```powershell
cd c:\Users\HP\OneDrive\Desktop\sesd\TeamFinder
pip install -r requirements.txt
```

### 3. Initialize the Database & Indexes
Run the initialization script to create collections, indexes, the administrator account, and initial demo data:

```powershell
python database/init_db.py
```

### 4. Run the Application
Start the Flask development server:

```powershell
python app.py
```

Access the application in your browser:
**http://127.0.0.1:5000**

---

## 🔑 Default Credentials

### Administrator Account
- **Email**: `admin@teamfinder.edu`
- **Password**: `AdminPassword123!`
- **Access**: Full platform overview, user management, and project moderation at `/admin`.

### Demo Student Accounts
| Student Name | Email | Password | Role / Primary Skills |
| :--- | :--- | :--- | :--- |
| **Aarav Sharma** | `aarav.sharma@college.edu` | `Password123!` | Python, Flask, MongoDB, Docker |
| **Diya Patel** | `diya.patel@college.edu` | `Password123!` | React, Bootstrap 5, UI/UX, JS |
| **Rohan Verma** | `rohan.verma@college.edu` | `Password123!` | NLP, FastAPI, Machine Learning |
| **Ananya Iyer** | `ananya.iyer@college.edu` | `Password123!` | Java, Spring Boot, Cybersecurity |
| **Kavya Reddy** | `kavya.reddy@college.edu` | `Password123!` | IoT, Embedded Systems, MQTT, C++ |

*(Clickable demo login pills are also provided directly on the Login page for convenience!)*

---

## 📡 REST API Reference

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Register new student profile | No |
| `POST` | `/api/auth/login` | Student / Admin login | No |
| `POST` | `/api/auth/logout` | Session termination | Yes |
| `GET` | `/api/auth/me` | Fetch active session & profile | Yes |
| `GET` | `/api/students` | Search and filter students by skills | Yes |
| `GET` | `/api/profiles/<user_id>` | Get specific student profile | Yes |
| `PUT` | `/api/profiles/me` | Update personal profile | Yes |
| `GET` | `/api/projects` | List projects with filters (`q`, `skill`, `status`) | Yes |
| `POST` | `/api/projects` | Create a new collaborative project | Student |
| `GET` | `/api/projects/<id>` | Retrieve project and team roster | Yes |
| `PUT` | `/api/projects/<id>` | Update project details | Owner/Admin |
| `DELETE`| `/api/projects/<id>` | Delete project and team data | Owner/Admin |
| `POST` | `/api/projects/<id>/request` | Submit join request to project owner | Student |
| `GET` | `/api/requests/received` | Fetch requests received for user's projects | Student |
| `GET` | `/api/requests/sent` | Fetch requests sent by user | Student |
| `POST` | `/api/requests/<id>/accept` | Accept join request & update team roster | Owner |
| `POST` | `/api/requests/<id>/reject` | Reject join request | Owner |
| `GET` | `/api/my-teams` | Retrieve all owned and joined teams | Student |
| `GET` | `/api/admin/stats` | Platform metrics & counters | Admin |
| `GET` | `/api/admin/users` | List all users and profiles | Admin |
| `POST` | `/api/admin/users/<id>/toggle-status` | Activate/deactivate user | Admin |
| `DELETE`| `/api/admin/users/<id>` | Delete user account | Admin |
| `GET` | `/api/admin/projects` | List all platform projects | Admin |
