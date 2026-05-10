from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase

from core.models import (
    Comment, EditProposal, Ingredient, Profile, Recipe, Region, Report, Technique,
)
from view import _fuzzy_match, _parse_positive_int


def make_user(email, **profile_kwargs):
    user = User.objects.create_user(username=email, email=email, password='pw',
                                    first_name='F', last_name='L')
    region = profile_kwargs.pop('region', None)
    if region is None:
        region, _ = Region.objects.get_or_create(name='Spain')
    Profile.objects.create(
        user=user, sharing_region=region, description='bio',
        date_of_birth=date(1990, 1, 1), gender='male', **profile_kwargs,
    )
    return user


class ParsePositiveIntTests(TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(_parse_positive_int(''))
        self.assertIsNone(_parse_positive_int(None))
        self.assertIsNone(_parse_positive_int('   '))

    def test_zero_returns_none(self):
        # 0 in cook_max used to nuke results; now treated as "no limit".
        self.assertIsNone(_parse_positive_int('0'))

    def test_negative_returns_none(self):
        self.assertIsNone(_parse_positive_int('-5'))

    def test_non_numeric_returns_none(self):
        self.assertIsNone(_parse_positive_int('abc'))
        self.assertIsNone(_parse_positive_int('30min'))

    def test_positive_int_returns_value(self):
        self.assertEqual(_parse_positive_int('30'), 30)
        self.assertEqual(_parse_positive_int('  45 '), 45)


class FuzzyMatchTests(TestCase):
    def test_no_correction_when_substring_matches(self):
        self.assertIsNone(_fuzzy_match('saff', ['Saffron', 'Salt']))

    def test_corrects_typo(self):
        self.assertEqual(_fuzzy_match('saffrn', ['Saffron', 'Salt']), 'Saffron')

    def test_returns_none_when_no_close_match(self):
        self.assertIsNone(_fuzzy_match('xyz', ['Saffron', 'Salt']))

    def test_case_insensitive(self):
        self.assertEqual(_fuzzy_match('SAFFRN', ['Saffron']), 'Saffron')


class RecipeSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name='Spain')
        cls.user = make_user('chef@example.com', region=cls.region)
        cls.saffron = Ingredient.objects.create(author=cls.user, name='Saffron')
        cls.salt = Ingredient.objects.create(author=cls.user, name='Salt')
        cls.braising = Technique.objects.create(
            author=cls.user, name='Braising', description='Slow-cook in liquid')
        cls.braising.regions.add(cls.region)

        cls.quick = Recipe.objects.create(
            author=cls.user, title='Quick Toast', content='Toast bread',
            cook_time=10, difficulty='Easy')
        cls.quick.regions.add(cls.region)
        cls.quick.ingredients.add(cls.salt)

        cls.paella = Recipe.objects.create(
            author=cls.user, title='Paella', content='Cook rice with saffron',
            cook_time=60, difficulty='Hard',
            cultural_significance='Valencian heritage dish')
        cls.paella.regions.add(cls.region)
        cls.paella.ingredients.add(cls.saffron)
        cls.paella.techniques.add(cls.braising)

    def setUp(self):
        self.client = Client()

    def test_no_filters_returns_all(self):
        r = self.client.get('/recipes/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(self.paella, r.context['recipes'])
        self.assertIn(self.quick, r.context['recipes'])
        self.assertFalse(r.context['any_filter'])

    def test_title_filter(self):
        r = self.client.get('/recipes/', {'title': 'paella'})
        self.assertIn(self.paella, r.context['recipes'])
        self.assertNotIn(self.quick, r.context['recipes'])

    def test_cook_time_min_filter(self):
        r = self.client.get('/recipes/', {'cook_min': '30'})
        self.assertIn(self.paella, r.context['recipes'])
        self.assertNotIn(self.quick, r.context['recipes'])

    def test_cook_time_max_filter(self):
        r = self.client.get('/recipes/', {'cook_max': '30'})
        self.assertIn(self.quick, r.context['recipes'])
        self.assertNotIn(self.paella, r.context['recipes'])

    def test_cook_time_zero_max_treated_as_unlimited(self):
        # Regression: previously cook_max=0 filtered cook_time<=0 → empty.
        r = self.client.get('/recipes/', {'cook_max': '0'})
        self.assertIn(self.paella, r.context['recipes'])
        self.assertIn(self.quick, r.context['recipes'])

    def test_cook_time_range(self):
        r = self.client.get('/recipes/', {'cook_min': '5', 'cook_max': '20'})
        self.assertIn(self.quick, r.context['recipes'])
        self.assertNotIn(self.paella, r.context['recipes'])

    def test_cook_time_swapped_range_auto_corrects(self):
        # User accidentally swaps min/max — should still work.
        r = self.client.get('/recipes/', {'cook_min': '20', 'cook_max': '5'})
        self.assertIn(self.quick, r.context['recipes'])

    def test_cook_time_non_numeric_ignored(self):
        r = self.client.get('/recipes/', {'cook_min': 'abc'})
        self.assertEqual(len(list(r.context['recipes'])), 2)

    def test_difficulty_filter(self):
        r = self.client.get('/recipes/', {'difficulty': 'Hard'})
        self.assertIn(self.paella, r.context['recipes'])
        self.assertNotIn(self.quick, r.context['recipes'])

    def test_ingredient_tag_filter(self):
        r = self.client.get('/recipes/', {'ingredient': 'saffron'})
        self.assertIn(self.paella, r.context['recipes'])
        self.assertNotIn(self.quick, r.context['recipes'])

    def test_ingredient_fuzzy_autocorrect(self):
        # "saffrn" doesn't substring-match anything but is close to "Saffron".
        r = self.client.get('/recipes/', {'ingredient': 'saffrn'})
        self.assertEqual(r.context['ingredient_corrected'], 'Saffron')
        self.assertIn(self.paella, r.context['recipes'])

    def test_technique_tag_filter(self):
        r = self.client.get('/recipes/', {'technique': 'brais'})
        self.assertIn(self.paella, r.context['recipes'])

    def test_technique_fuzzy_autocorrect(self):
        r = self.client.get('/recipes/', {'technique': 'brasing'})
        self.assertEqual(r.context['technique_corrected'], 'Braising')
        self.assertIn(self.paella, r.context['recipes'])

    def test_cultural_significance_filter(self):
        r = self.client.get('/recipes/', {'cultural': 'Valencian'})
        self.assertIn(self.paella, r.context['recipes'])
        self.assertNotIn(self.quick, r.context['recipes'])

    def test_any_filter_flag(self):
        r = self.client.get('/recipes/', {'title': 'paella'})
        self.assertTrue(r.context['any_filter'])


class IngredientSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('chef@example.com')
        cls.saffron = Ingredient.objects.create(
            author=cls.user, name='Saffron', description='Crocus stigmas')
        cls.salt = Ingredient.objects.create(author=cls.user, name='Salt')

    def setUp(self):
        self.client = Client()
        self.client.login(username='chef@example.com', password='pw')

    def test_name_filter(self):
        r = self.client.get('/ingredients/', {'name': 'saff'})
        self.assertIn(self.saffron, r.context['ingredients'])
        self.assertNotIn(self.salt, r.context['ingredients'])

    def test_name_fuzzy_autocorrect(self):
        r = self.client.get('/ingredients/', {'name': 'saffrn'})
        self.assertEqual(r.context['name_corrected'], 'Saffron')
        self.assertIn(self.saffron, r.context['ingredients'])

    def test_description_filter(self):
        r = self.client.get('/ingredients/', {'description': 'crocus'})
        self.assertIn(self.saffron, r.context['ingredients'])
        self.assertNotIn(self.salt, r.context['ingredients'])

    def test_datalist_context_present(self):
        r = self.client.get('/ingredients/')
        names = list(r.context['all_ingredient_names'])
        self.assertIn('Saffron', names)
        self.assertIn('Salt', names)


class TechniqueSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name='France')
        cls.user = make_user('chef@example.com', region=cls.region)
        cls.sousvide = Technique.objects.create(
            author=cls.user, name='Sous Vide',
            description='Precision low-temp cooking',
            necessary_tools='immersion circulator, vacuum sealer')
        cls.sousvide.regions.add(cls.region)
        cls.braising = Technique.objects.create(
            author=cls.user, name='Braising', description='Slow-cook in liquid')
        cls.braising.regions.add(cls.region)

    def setUp(self):
        self.client = Client()
        self.client.login(username='chef@example.com', password='pw')

    def test_name_filter(self):
        r = self.client.get('/techniques/', {'name': 'sous'})
        self.assertIn(self.sousvide, r.context['techniques'])
        self.assertNotIn(self.braising, r.context['techniques'])

    def test_name_fuzzy_autocorrect(self):
        r = self.client.get('/techniques/', {'name': 'brasing'})
        self.assertEqual(r.context['name_corrected'], 'Braising')

    def test_tools_filter(self):
        r = self.client.get('/techniques/', {'tools': 'circulator'})
        self.assertIn(self.sousvide, r.context['techniques'])
        self.assertNotIn(self.braising, r.context['techniques'])

    def test_region_filter(self):
        r = self.client.get('/techniques/', {'region': 'France'})
        self.assertIn(self.sousvide, r.context['techniques'])


class TechniqueModelTests(TestCase):
    def test_necessary_tools_optional(self):
        user = make_user('chef@example.com')
        t = Technique.objects.create(author=user, name='Pan-frying',
                                     description='Cook in a pan')
        self.assertEqual(t.necessary_tools, '')

    def test_necessary_tools_stored(self):
        user = make_user('chef@example.com')
        t = Technique.objects.create(author=user, name='Sous Vide',
                                     description='Low-temp cooking',
                                     necessary_tools='circulator')
        t.refresh_from_db()
        self.assertEqual(t.necessary_tools, 'circulator')


class RecipeLikeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name='Spain')
        cls.author = make_user('author@example.com', region=cls.region)
        cls.viewer = make_user('viewer@example.com', region=cls.region)
        cls.recipe = Recipe.objects.create(
            author=cls.author, title='Paella', content='...',
            cook_time=60, difficulty='Hard')

    def setUp(self):
        self.client = Client()
        self.client.login(username='viewer@example.com', password='pw')

    def test_like_toggle_adds_then_removes(self):
        url = f'/recipes/{self.recipe.pk}/like/'
        self.client.post(url)
        self.assertTrue(self.recipe.liked_by.filter(pk=self.viewer.pk).exists())
        self.client.post(url)
        self.assertFalse(self.recipe.liked_by.filter(pk=self.viewer.pk).exists())


class CommentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('chef@example.com')
        cls.recipe = Recipe.objects.create(
            author=cls.user, title='Toast', content='...', cook_time=5)

    def setUp(self):
        self.client = Client()
        self.client.login(username='chef@example.com', password='pw')

    def test_add_top_level_comment(self):
        r = self.client.post(f'/comments/recipe/{self.recipe.pk}/add/',
                             {'body': 'Looks great'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Comment.objects.filter(recipe=self.recipe).count(), 1)

    def test_empty_body_ignored(self):
        self.client.post(f'/comments/recipe/{self.recipe.pk}/add/', {'body': '   '})
        self.assertEqual(Comment.objects.count(), 0)

    def test_reply_chains_to_parent(self):
        parent = Comment.objects.create(author=self.user, body='top',
                                        recipe=self.recipe)
        self.client.post(f'/comments/recipe/{self.recipe.pk}/add/',
                         {'body': 'reply', 'parent_id': str(parent.pk)})
        reply = Comment.objects.exclude(pk=parent.pk).get()
        self.assertEqual(reply.parent_id, parent.pk)


class ReportFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name='Spain')
        cls.author = make_user('author@example.com', region=cls.region)
        cls.reporter = make_user('reporter@example.com', region=cls.region)
        cls.admin = make_user('admin@example.com', region=cls.region)
        cls.admin.is_staff = True
        cls.admin.save(update_fields=['is_staff'])
        cls.recipe = Recipe.objects.create(
            author=cls.author, title='Bad Recipe', content='...', cook_time=10)

    def setUp(self):
        self.client = Client()

    def test_submit_report(self):
        self.client.login(username='reporter@example.com', password='pw')
        r = self.client.post(f'/reports/recipe/{self.recipe.pk}/submit/',
                             {'reason': 'spam'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(Report.objects.get().status, 'pending')

    def test_non_staff_blocked_from_inbox(self):
        self.client.login(username='reporter@example.com', password='pw')
        r = self.client.get('/reports/')
        self.assertEqual(r.status_code, 403)

    def test_staff_can_view_inbox(self):
        self.client.login(username='admin@example.com', password='pw')
        r = self.client.get('/reports/')
        self.assertEqual(r.status_code, 200)

    def test_admin_delete_entry_action(self):
        report = Report.objects.create(reporter=self.reporter,
                                       recipe=self.recipe, reason='spam')
        self.client.login(username='admin@example.com', password='pw')
        self.client.post(f'/reports/{report.pk}/action/',
                         {'action': 'delete_entry'})
        self.assertFalse(Recipe.objects.filter(pk=self.recipe.pk).exists())

    def test_admin_ban_user_action(self):
        report = Report.objects.create(reporter=self.reporter,
                                       recipe=self.recipe, reason='spam')
        self.client.login(username='admin@example.com', password='pw')
        self.client.post(f'/reports/{report.pk}/action/', {'action': 'ban_user'})
        self.author.refresh_from_db()
        self.assertFalse(self.author.is_active)


class EditProposalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name='Spain')
        cls.author = make_user('author@example.com', region=cls.region)
        cls.proposer = make_user('proposer@example.com', region=cls.region)
        cls.recipe = Recipe.objects.create(
            author=cls.author, title='Original', content='Original content',
            cook_time=10, difficulty='Easy', cultural_significance='heritage')

    def setUp(self):
        self.client = Client()

    def test_owner_edit_saves_immediately(self):
        self.client.login(username='author@example.com', password='pw')
        self.client.post(f'/recipes/{self.recipe.pk}/edit/', {
            'title': 'Updated', 'content': 'New content',
            'cultural_significance': 'heritage', 'cook_time': '20',
            'difficulty': 'Medium',
        })
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.title, 'Updated')
        self.assertEqual(EditProposal.objects.count(), 0)

    def test_non_owner_creates_pending_proposal(self):
        self.client.login(username='proposer@example.com', password='pw')
        self.client.post(f'/recipes/{self.recipe.pk}/edit/', {
            'title': 'Updated', 'content': 'New content',
            'cultural_significance': 'heritage', 'cook_time': '10',
            'difficulty': 'Easy',
        })
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.title, 'Original')
        proposal = EditProposal.objects.get()
        self.assertEqual(proposal.status, 'pending')
        self.assertIn('title', proposal.payload)


class CulinaryCompareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('chef@example.com')
        cls.r1 = Recipe.objects.create(author=cls.user, title='A',
                                       content='...', cook_time=10)
        cls.r2 = Recipe.objects.create(author=cls.user, title='B',
                                       content='...', cook_time=20)

    def setUp(self):
        self.client = Client()
        self.client.login(username='chef@example.com', password='pw')

    def test_compare_default_kind_is_recipe(self):
        r = self.client.get('/culinary-compare/')
        self.assertEqual(r.context['kind'], 'recipe')

    def test_compare_two_recipes_produces_rows(self):
        r = self.client.get('/culinary-compare/',
                            {'kind': 'recipe', 'ids': [self.r1.pk, self.r2.pk]})
        self.assertEqual(len(r.context['selected']), 2)
        self.assertTrue(len(r.context['rows']) > 0)

    def test_compare_single_selection_shows_too_few(self):
        r = self.client.get('/culinary-compare/',
                            {'kind': 'recipe', 'ids': [self.r1.pk]})
        self.assertTrue(r.context['too_few'])
        self.assertEqual(r.context['rows'], [])
