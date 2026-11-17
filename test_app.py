import unittest
import json
from bson import ObjectId
from app import app
from config import get_db

class TeamFinderTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.db = get_db()

    def test_01_index_page(self):
        """Test landing page loads successfully."""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'TeamFinder', res.data)
        self.assertIn(b'CAMPUS', res.data)

    def test_02_student_registration_and_login(self):
        """Test registering a new student and logging in."""
        test_email = "test.student@college.edu"
        # Clean up any existing test user
        self.db.users.delete_one({"email": test_email})
        self.db.student_profiles.delete_one({"email": test_email})

        reg_data = {
            "name": "Test Student",
            "email": test_email,
            "password": "SecretPassword123!",
            "confirm_password": "SecretPassword123!",
            "college": "Test Tech Institute",
            "department": "CSE",
            "skills": "Python, Flask, Docker",
            "interests": "Cloud Computing",
            "bio": "I am a test student."
        }
        res = self.client.post('/api/auth/register', json=reg_data)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Check in MongoDB
        user_doc = self.db.users.find_one({"email": test_email})
        self.assertIsNotNone(user_doc)
        self.assertEqual(user_doc["role"], "student")

        profile_doc = self.db.student_profiles.find_one({"email": test_email})
        self.assertIsNotNone(profile_doc)
        self.assertIn("Python", profile_doc["skills"])

        # Test login
        login_res = self.client.post('/api/auth/login', json={
            "email": test_email,
            "password": "SecretPassword123!"
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertTrue(login_res.get_json()["success"])

    def test_03_duplicate_registration_prevented(self):
        """Test that registering duplicate email returns error."""
        reg_data = {
            "name": "Duplicate Student",
            "email": "aarav.sharma@college.edu", # existing demo student
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        res = self.client.post('/api/auth/register', json=reg_data)
        self.assertEqual(res.status_code, 409)

    def test_04_project_lifecycle_and_team_flow(self):
        """Test project creation, search, join request, and capacity check."""
        # 1. Login as Aarav
        login_res = self.client.post('/api/auth/login', json={
            "email": "aarav.sharma@college.edu",
            "password": "Password123!"
        })
        self.assertEqual(login_res.status_code, 200)

        # 2. Create a project with team_size = 2
        proj_payload = {
            "title": "Automated Unit Test Project",
            "description": "Testing full-stack end-to-end integration with MongoDB.",
            "team_size": 2,
            "status": "Open",
            "skills_required": "Python, PyMongo, Flask"
        }
        create_res = self.client.post('/api/projects', json=proj_payload)
        self.assertEqual(create_res.status_code, 201)
        project_id = create_res.get_json()["project_id"]

        # 3. Check project search
        search_res = self.client.get('/api/projects?skill=PyMongo')
        self.assertEqual(search_res.status_code, 200)
        projects = search_res.get_json()["projects"]
        self.assertTrue(any(p["_id"] == project_id for p in projects))

        # 4. Logout Aarav
        self.client.post('/api/auth/logout')

        # 5. Login as Diya
        self.client.post('/api/auth/login', json={
            "email": "diya.patel@college.edu",
            "password": "Password123!"
        })

        # 6. Diya sends join request to the newly created project
        req_res = self.client.post(f'/api/projects/{project_id}/request', json={
            "message": "I would love to participate in this project!"
        })
        self.assertEqual(req_res.status_code, 201)

        # 7. Diya tries to send duplicate request -> must be rejected
        dup_res = self.client.post(f'/api/projects/{project_id}/request', json={
            "message": "Another request"
        })
        self.assertEqual(dup_res.status_code, 409)

        # 8. Logout Diya and Login as Aarav to accept
        self.client.post('/api/auth/logout')
        self.client.post('/api/auth/login', json={
            "email": "aarav.sharma@college.edu",
            "password": "Password123!"
        })

        # Get received requests
        rec_res = self.client.get('/api/requests/received')
        self.assertEqual(rec_res.status_code, 200)
        rec_list = rec_res.get_json()["requests"]
        target_req = next((r for r in rec_list if r["project_id"] == project_id), None)
        self.assertIsNotNone(target_req)

        # Accept the request
        accept_res = self.client.post(f'/api/requests/{target_req["_id"]}/accept')
        self.assertEqual(accept_res.status_code, 200)
        self.assertTrue(accept_res.get_json()["success"])

        # Check that team is now full (size 2 reached: Aarav + Diya)
        proj_check = self.client.get(f'/api/projects/{project_id}')
        self.assertEqual(proj_check.status_code, 200)
        p_data = proj_check.get_json()
        self.assertEqual(p_data["current_members"], 2)

        # 9. Clean up test project
        del_res = self.client.delete(f'/api/projects/{project_id}')
        self.assertEqual(del_res.status_code, 200)

    def test_05_admin_operations(self):
        """Test admin metrics and user management."""
        login_res = self.client.post('/api/auth/login', json={
            "email": "admin@teamfinder.edu",
            "password": "AdminPassword123!"
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertEqual(login_res.get_json()["role"], "admin")

        stats_res = self.client.get('/api/admin/stats')
        self.assertEqual(stats_res.status_code, 200)
        stats = stats_res.get_json()
        self.assertGreaterEqual(stats["total_users"], 1)
        self.assertGreaterEqual(stats["total_students"], 1)

if __name__ == "__main__":
    unittest.main()
