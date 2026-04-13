from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.models import Ingredient, Profile, Recipe, Region, Technique


def index(request):
    if request.user.is_authenticated:
        return redirect('/entry/')
    recipes = Recipe.objects.select_related('author').prefetch_related('regions')[:6]
    return render(request, 'index.html', {'recipes': recipes})


def recipes_page(request):
    recipes = (Recipe.objects.select_related('author')
               .prefetch_related('regions')[:30])
    return render(request, 'recipes.html', {'recipes': recipes})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def login_page(request):
    if request.user.is_authenticated:
        return redirect('/entry/')
    error = ''
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        password = request.POST.get('password') or ''
        try:
            candidate = User.objects.get(email__iexact=email)
            user = authenticate(request, username=candidate.username, password=password)
        except User.DoesNotExist:
            user = None
        if user is not None:
            login(request, user)
            return redirect('/entry/')
        error = 'Invalid email or password.'
    return render(request, 'login.html', {'error': error})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def register_page(request):
    if request.user.is_authenticated:
        return redirect('/entry/')
    error = ''
    success = ''
    if request.method == 'POST':
        first_name = (request.POST.get('first_name') or '').strip()
        last_name = (request.POST.get('last_name') or '').strip()
        email = (request.POST.get('email') or '').strip().lower()
        password = request.POST.get('password') or ''
        if not all([first_name, last_name, email, password]):
            error = 'All fields are required.'
        elif User.objects.filter(email__iexact=email).exists():
            error = 'An account with this email already exists.'
        else:
            try:
                User.objects.create_user(
                    username=email, email=email, password=password,
                    first_name=first_name, last_name=last_name,
                )
                success = 'Account created! You can log in now.'
            except IntegrityError:
                error = 'Could not register. Please try again.'
    return render(request, 'register.html', {
        'error': error, 'success': success,
    })


def logout_view(request):
    logout(request)
    return HttpResponseRedirect('/')


@csrf_exempt
@login_required
@require_http_methods(["GET", "POST"])
def profile_page(request):
    profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'description': ''})
    error = ''
    success = ''
    required_msg = 'Complete your profile to start adding recipes.' if request.GET.get('required') else ''

    if request.method == 'POST':
        region_id = (request.POST.get('region_id') or '').strip()
        description = (request.POST.get('description') or '').strip()
        dob = (request.POST.get('date_of_birth') or '').strip()
        gender = (request.POST.get('gender') or '').strip()
        photo = request.FILES.get('profile_photo')

        # If region already locked, use existing
        if profile.sharing_region_id:
            region_id = str(profile.sharing_region_id)

        missing = []
        if not region_id: missing.append('country')
        if not description: missing.append('about me')
        if not dob: missing.append('date of birth')
        if not gender: missing.append('gender')

        if missing:
            error = f"Required: {', '.join(missing)}."
        elif not Region.objects.filter(pk=region_id).exists():
            error = 'Selected country does not exist.'
        else:
            if not profile.sharing_region_id:
                profile.sharing_region_id = region_id
            profile.description = description
            profile.date_of_birth = dob
            profile.gender = gender
            if photo:
                profile.profile_photo = photo
            try:
                profile.save()
                success = 'Profile saved successfully.'
            except ValidationError as e:
                error = str(e)

    return render(request, 'profile.html', {
        'profile': profile,
        'regions': Region.objects.all(),
        'error': error,
        'success': success,
        'required_msg': required_msg,
    })


@login_required
def culinary_road_page(request):
    return render(request, 'culinary_road.html')


@login_required
def culinary_data_page(request):
    return render(request, 'culinary_data.html')


def _parse_region_ids(request):
    ids = request.POST.getlist('region_ids')
    valid = list(Region.objects.filter(pk__in=ids).values_list('pk', flat=True))
    return valid


@login_required
def entry_page(request):
    profile = getattr(request.user, 'profile', None)
    region = profile.sharing_region if profile else None
    my_recipes = (Recipe.objects.filter(author=request.user)
                  .select_related('author').prefetch_related('regions')[:8])
    others_recipes = (Recipe.objects.exclude(author=request.user)
                      .select_related('author').prefetch_related('regions')[:8])
    return render(request, 'entry.html', {
        'region_name': region.name if region else 'No region selected',
        'my_recipes': my_recipes,
        'others_recipes': others_recipes,
    })


@csrf_exempt
@login_required
@require_http_methods(["GET", "POST"])
def add_recipe_page(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_complete():
        return redirect('/profile/?required=1')
    error = ''
    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        content = (request.POST.get('content') or '').strip()
        cook_time = request.POST.get('cook_time') or '30'
        difficulty = request.POST.get('difficulty') or 'Easy'
        image = request.FILES.get('image')
        cultural_significance = (request.POST.get('cultural_significance') or '').strip()
        region_ids = _parse_region_ids(request)
        ingredient_ids = list(Ingredient.objects.filter(
            pk__in=request.POST.getlist('ingredient_ids')
        ).values_list('pk', flat=True))
        technique_ids = list(Technique.objects.filter(
            pk__in=request.POST.getlist('technique_ids')
        ).values_list('pk', flat=True))
        if not title or not content or not cultural_significance:
            error = 'Title, instructions and cultural significance are required.'
        elif not region_ids:
            error = 'Select at least one country.'
        else:
            try:
                cook_time_val = max(1, int(cook_time))
            except ValueError:
                cook_time_val = 30
            recipe = Recipe.objects.create(
                author=request.user, title=title, content=content,
                image=image, cook_time=cook_time_val, difficulty=difficulty,
                cultural_significance=cultural_significance,
            )
            recipe.regions.set(region_ids)
            recipe.ingredients.set(ingredient_ids)
            recipe.techniques.set(technique_ids)
            return redirect('/entry/')
    return render(request, 'add_recipe.html', {
        'error': error,
        'regions': Region.objects.all(),
        'all_ingredients': Ingredient.objects.all(),
        'all_techniques': Technique.objects.all(),
    })


@login_required
def recipe_detail_page(request, pk):
    recipe = get_object_or_404(
        Recipe.objects.select_related('author').prefetch_related('regions', 'ingredients', 'techniques'),
        pk=pk,
    )
    return render(request, 'recipe_detail.html', {'recipe': recipe})


@login_required
def technique_detail_page(request, pk):
    technique = get_object_or_404(
        Technique.objects.select_related('author').prefetch_related('regions'),
        pk=pk,
    )
    return render(request, 'technique_detail.html', {'technique': technique})


@login_required
def ingredient_detail_page(request, pk):
    ingredient = get_object_or_404(
        Ingredient.objects.select_related('author').prefetch_related('regions'),
        pk=pk,
    )
    return render(request, 'ingredient_detail.html', {'ingredient': ingredient})


@login_required
def techniques_page(request):
    return render(request, 'techniques.html', {
        'techniques': Technique.objects.select_related('author').prefetch_related('regions'),
    })


@csrf_exempt
@login_required
@require_http_methods(["GET", "POST"])
def add_technique_page(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_complete():
        return redirect('/profile/?required=1')
    error = ''
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        description = (request.POST.get('description') or '').strip()
        cultural_significance = (request.POST.get('cultural_significance') or '').strip()
        region_ids = _parse_region_ids(request)
        if not name or not description or not cultural_significance:
            error = 'Name, description and cultural significance are required.'
        elif not region_ids:
            error = 'Select at least one country.'
        else:
            technique = Technique.objects.create(
                author=request.user, name=name, description=description,
                cultural_significance=cultural_significance,
            )
            technique.regions.set(region_ids)
            return redirect('/techniques/')
    return render(request, 'add_technique.html', {
        'error': error,
        'regions': Region.objects.all(),
    })


@login_required
def ingredients_page(request):
    return render(request, 'ingredients.html', {
        'ingredients': Ingredient.objects.select_related('author').prefetch_related('regions'),
    })


@csrf_exempt
@login_required
@require_http_methods(["GET", "POST"])
def add_ingredient_page(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_complete():
        return redirect('/profile/?required=1')
    error = ''
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        description = (request.POST.get('description') or '').strip()
        cultural_significance = (request.POST.get('cultural_significance') or '').strip()
        region_ids = _parse_region_ids(request)
        if not name or not description or not cultural_significance:
            error = 'Name, description and cultural significance are required.'
        elif not region_ids:
            error = 'Select at least one country.'
        else:
            ingredient = Ingredient.objects.create(
                author=request.user, name=name, description=description,
                cultural_significance=cultural_significance,
            )
            ingredient.regions.set(region_ids)
            return redirect('/ingredients/')
    return render(request, 'add_ingredient.html', {
        'error': error,
        'regions': Region.objects.all(),
    })
