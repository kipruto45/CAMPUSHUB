"""
Tests for activity app
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class ActivityModelTest(TestCase):
    """Test cases for Activity models"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_activity_creation(self):
        """Test activity model creation"""
        # Basic test - to be expanded
        self.assertIsNotNone(self.user)
    
    def test_activity_str(self):
        """Test activity string representation"""
        self.assertIsNotNone(str(self.user))
