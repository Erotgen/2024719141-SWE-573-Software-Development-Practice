import os
import sys
import unittest

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import django
django.setup()

from django.core.management import call_command
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.client import Client

from core.models import Ingredient, Profile, Recipe, Region, Technique


_SCHEMA_READY = False


def _ensure_schema():
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    call_command('migrate', '--run-syncdb', verbosity=0, interactive=False)
    _SCHEMA_READY = True


def _truncate_all():
    tables = [
        'core_recipe_regions', 'core_recipe_ingredients', 'core_recipe_techniques',
        'core_recipe', 'core_ingredient_regions', 'core_ingredient',
        'core_technique_regions', 'core_technique',
        'core_profile', 'core_region',
        'auth_user_groups', 'auth_user_user_permissions', 'auth_user',
        'django_session',
    ]
    with connection.cursor() as cur:
        for t in tables:
            try:
                cur.execute(f'DELETE FROM {t}')
            except Exception:
                pass


class DjangoUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_schema()

    def setUp(self):
        _truncate_all()
        self.client = Client()


class RegionModelTests(DjangoUnitTest):
    def test_str_returns_name(self):
        self.assertEqual(str(Region.objects.create(name='Italy')), 'Italy')

    def test_name_unique(self):
        Region.objects.create(name='France')
        with self.assertRaises(Exception):
            Region.objects.create(name='France')


class ProfileModelTests(DjangoUnitTest):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='u@x.com', email='u@x.com', password='pw')
        self.region = Region.objects.create(name='Spain')

    def test_is_complete_false_when_missing_fields(self):
        self.assertFalse(Profile.objects.create(user=self.user).is_complete())

    def test_is_complete_true_when_all_fields(self):
        profile = Profile.objects.create(
            user=self.user, sharing_region=self.region,
            description='hi', date_of_birth='1990-01-01', gender='male',
        )
        self.assertTrue(profile.is_complete())

    def test_sharing_region_cannot_change_after_set(self):
        profile = Profile.objects.create(user=self.user, sharing_region=self.region)
        profile.sharing_region = Region.objects.create(name='Greece')
        with self.assertRaises(ValidationError):
            profile.save()

    def test_sharing_region_can_be_set_initially(self):
        profile = Profile.objects.create(user=self.user)
        profile.sharing_region = self.region
        profile.save()
        profile.refresh_from_db()
        self.assertEqual(profile.sharing_region_id, self.region.pk)


class RecipeModelTests(DjangoUnitTest):
    def test_recipe_create_with_defaults(self):
        user = User.objects.create_user(username='a@b.com', email='a@b.com', password='pw')
        recipe = Recipe.objects.create(author=user, title='Pasta', content='boil')
        self.assertEqual(recipe.cook_time, 30)
        self.assertEqual(recipe.difficulty, 'Easy')
        self.assertEqual(str(recipe), 'Pasta')


class AuthViewTests(DjangoUnitTest):
    def test_register_creates_user(self):
        resp = self.client.post('/register/', {
            'first_name': 'A', 'last_name': 'B',
            'email': 'new@example.com', 'password': 'secret123',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(User.objects.filter(email='new@example.com').exists())

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(username='dup@x.com', email='dup@x.com', password='pw')
        resp = self.client.post('/register/', {
            'first_name': 'A', 'last_name': 'B',
            'email': 'dup@x.com', 'password': 'secret123',
        })
        self.assertIn(b'already exists', resp.content)

    def test_register_rejects_missing_fields(self):
        resp = self.client.post('/register/', {
            'first_name': '', 'last_name': '', 'email': '', 'password': '',
        })
        self.assertIn(b'All fields are required', resp.content)

    def test_login_success_redirects_to_entry(self):
        User.objects.create_user(username='log@x.com', email='log@x.com', password='pw12345')
        resp = self.client.post('/login/', {'email': 'log@x.com', 'password': 'pw12345'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/entry/')

    def test_login_invalid_credentials(self):
        resp = self.client.post('/login/', {'email': 'nobody@x.com', 'password': 'x'})
        self.assertIn(b'Invalid email or password', resp.content)

    def test_logout_redirects_home(self):
        User.objects.create_user(username='o@x.com', email='o@x.com', password='pw')
        self.client.login(username='o@x.com', password='pw')
        resp = self.client.get('/logout/')
        self.assertEqual(resp.status_code, 302)


class RecipeViewTests(DjangoUnitTest):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='c@x.com', email='c@x.com', password='pw')
        self.region = Region.objects.create(name='Mexico')
        Profile.objects.create(
            user=self.user, sharing_region=self.region,
            description='me', date_of_birth='1990-01-01', gender='male',
        )
        self.client.login(username='c@x.com', password='pw')

    def test_add_recipe_requires_profile_complete(self):
        user2 = User.objects.create_user(username='d@x.com', email='d@x.com', password='pw')
        Profile.objects.create(user=user2)
        c2 = Client()
        c2.login(username='d@x.com', password='pw')
        resp = c2.get('/recipes/add/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/profile/?required=1')

    def test_add_recipe_success(self):
        resp = self.client.post('/recipes/add/', {
            'title': 'Tacos', 'content': 'make them',
            'cultural_significance': 'cultural',
            'region_ids': [self.region.pk],
            'cook_time': '20', 'difficulty': 'Easy',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/entry/')
        self.assertTrue(Recipe.objects.filter(title='Tacos').exists())

    def test_add_recipe_missing_fields(self):
        resp = self.client.post('/recipes/add/', {
            'title': '', 'content': '', 'cultural_significance': '',
            'region_ids': [self.region.pk],
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'required', resp.content)

    def test_add_recipe_missing_region(self):
        resp = self.client.post('/recipes/add/', {
            'title': 'X', 'content': 'y', 'cultural_significance': 'z',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'at least one country', resp.content)

    def test_add_technique_success(self):
        resp = self.client.post('/techniques/add/', {
            'name': 'Grill', 'description': 'heat',
            'cultural_significance': 'cult',
            'region_ids': [self.region.pk],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/techniques/')
        self.assertTrue(Technique.objects.filter(name='Grill').exists())

    def test_add_ingredient_success(self):
        resp = self.client.post('/ingredients/add/', {
            'name': 'Chili', 'description': 'hot',
            'cultural_significance': 'cult',
            'region_ids': [self.region.pk],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/ingredients/')
        self.assertTrue(Ingredient.objects.filter(name='Chili').exists())


class IndexViewTests(DjangoUnitTest):
    def test_index_anonymous_renders(self):
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_index_authenticated_redirects(self):
        User.objects.create_user(username='i@x.com', email='i@x.com', password='pw')
        self.client.login(username='i@x.com', password='pw')
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/entry/')


if __name__ == '__main__':
    unittest.main()
