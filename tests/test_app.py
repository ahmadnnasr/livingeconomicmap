
import os, unittest
os.environ.setdefault("DATABASE_URL","sqlite:///./test_lemp.db")
os.environ.setdefault("DASHBOARD_USERNAME","admin")
os.environ.setdefault("DASHBOARD_PASSWORD","password")
from fastapi.testclient import TestClient
from app.main import app
class AppTests(unittest.TestCase):
    def setUp(self): self.client=TestClient(app)
    def test_health(self): self.assertEqual(self.client.get('/health').status_code,200)
    def test_dashboard_requires_auth(self): self.assertEqual(self.client.get('/').status_code,401)
    def test_dashboard_auth(self): self.assertEqual(self.client.get('/',auth=('admin','password')).status_code,200)
    def test_api_auth(self): self.assertEqual(self.client.get('/api/state',auth=('admin','password')).status_code,200)
if __name__=='__main__': unittest.main()
