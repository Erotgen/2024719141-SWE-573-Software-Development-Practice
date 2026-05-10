import difflib
import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django.http import HttpResponseForbidden
from django.utils import timezone

from core.models import Comment, EditProposal, Ingredient, Profile, Recipe, Region, Report, Technique


_COMMENT_TARGETS = {
    'recipe': (Recipe, 'recipe'),
    'ingredient': (Ingredient, 'ingredient'),
    'technique': (Technique, 'technique'),
}

_EDIT_FIELDS = {
    'recipe': ['title', 'content', 'cultural_significance', 'cook_time', 'difficulty'],
    'ingredient': ['name', 'description'],
    'technique': ['name', 'description', 'cultural_significance', 'necessary_tools'],
}

_EDIT_LABELS = {
    'title': 'Title', 'name': 'Name',
    'content': 'Instructions', 'description': 'Description',
    'cultural_significance': 'Cultural Significance',
    'cook_time': 'Cook Time (min)', 'difficulty': 'Difficulty',
    'necessary_tools': 'Necessary Tools',
}

_EDIT_OPTIONAL = {'necessary_tools'}


def _comments_for(field, obj):
    return (Comment.objects.filter(parent__isnull=True, **{field: obj})
            .select_related('author')
            .prefetch_related('liked_by', 'disliked_by',
                              'replies__author', 'replies__liked_by', 'replies__disliked_by'))


def index(request):
    if request.user.is_authenticated:
        return redirect('/entry/')
    recipes = Recipe.objects.select_related('author').prefetch_related('regions')[:6]
    return render(request, 'index.html', {'recipes': recipes})


def _parse_positive_int(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        n = int(raw)
    except ValueError:
        return None
    return n if n > 0 else None


def _fuzzy_match(term, candidates):
    """Return the canonical candidate name when `term` doesn't substring-match
    any candidate but is close to one. Returns None if no correction needed
    or no close match exists."""
    term_l = term.lower()
    lowered = [c.lower() for c in candidates]
    if any(term_l in c for c in lowered):
        return None
    matches = difflib.get_close_matches(term_l, lowered, n=1, cutoff=0.7)
    if not matches:
        return None
    idx = lowered.index(matches[0])
    return candidates[idx]


def recipes_page(request):
    g = request.GET
    title = (g.get('title') or '').strip()
    author = (g.get('author') or '').strip()
    region = (g.get('region') or '').strip()
    difficulty = (g.get('difficulty') or '').strip()
    cook_min_raw = (g.get('cook_min') or '').strip()
    cook_max_raw = (g.get('cook_max') or '').strip()
    ingredient = (g.get('ingredient') or '').strip()
    technique = (g.get('technique') or '').strip()
    instructions = (g.get('instructions') or '').strip()
    cultural = (g.get('cultural') or '').strip()

    cook_min = _parse_positive_int(cook_min_raw)
    cook_max = _parse_positive_int(cook_max_raw)
    if cook_min is not None and cook_max is not None and cook_min > cook_max:
        cook_min, cook_max = cook_max, cook_min

    ingredient_corrected = ''
    technique_corrected = ''
    if ingredient:
        names = list(Ingredient.objects.values_list('name', flat=True))
        corrected = _fuzzy_match(ingredient, names)
        if corrected:
            ingredient_corrected = corrected
    if technique:
        names = list(Technique.objects.values_list('name', flat=True))
        corrected = _fuzzy_match(technique, names)
        if corrected:
            technique_corrected = corrected

    effective_ingredient = ingredient_corrected or ingredient
    effective_technique = technique_corrected or technique

    qs = Recipe.objects.select_related('author').prefetch_related('regions')
    if title:
        qs = qs.filter(title__icontains=title)
    if author:
        qs = qs.filter(Q(author__first_name__icontains=author)
                       | Q(author__last_name__icontains=author)
                       | Q(author__email__icontains=author))
    if region:
        qs = qs.filter(regions__name__icontains=region)
    if difficulty:
        qs = qs.filter(difficulty=difficulty)
    if cook_min is not None:
        qs = qs.filter(cook_time__gte=cook_min)
    if cook_max is not None:
        qs = qs.filter(cook_time__lte=cook_max)
    if effective_ingredient:
        qs = qs.filter(ingredients__name__icontains=effective_ingredient)
    if effective_technique:
        qs = qs.filter(techniques__name__icontains=effective_technique)
    if instructions:
        qs = qs.filter(content__icontains=instructions)
    if cultural:
        qs = qs.filter(cultural_significance__icontains=cultural)

    qs = qs.distinct()[:60]

    filters = {
        'title': title, 'author': author, 'region': region,
        'difficulty': difficulty,
        'cook_min': cook_min_raw, 'cook_max': cook_max_raw,
        'ingredient': ingredient, 'technique': technique,
        'instructions': instructions, 'cultural': cultural,
    }
    any_filter = any(filters.values())
    return render(request, 'recipes.html', {
        'recipes': qs,
        'filters': filters,
        'any_filter': any_filter,
        'difficulty_choices': ['Easy', 'Medium', 'Hard'],
        'all_ingredient_names': Ingredient.objects.values_list('name', flat=True).order_by('name'),
        'all_technique_names': Technique.objects.values_list('name', flat=True).order_by('name'),
        'ingredient_corrected': ingredient_corrected,
        'technique_corrected': technique_corrected,
    })


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
    pinned = (Recipe.objects
              .filter(latitude__isnull=False, longitude__isnull=False)
              .select_related('author'))
    points = []
    for r in pinned:
        image_url = ''
        if r.image and r.image.name:
            try:
                image_url = r.image.url
            except ValueError:
                image_url = ''
        points.append({
            'pk': r.pk,
            'title': r.title,
            'lat': r.latitude,
            'lng': r.longitude,
            'image_url': image_url,
            'cultural_significance': r.cultural_significance or '',
        })
    return render(request, 'culinary_road.html', {
        'points_json': json.dumps(points),
        'points_count': len(points),
    })


_COMPARE_KINDS = {
    'recipe': {
        'model': Recipe,
        'label': 'Recipes',
        'name_field': 'title',
        'fields': [
            ('title', 'Title'),
            ('author_name', 'Author'),
            ('regions_list', 'Regions'),
            ('cook_time', 'Cook Time (min)'),
            ('difficulty', 'Difficulty'),
            ('ingredients_list', 'Ingredients'),
            ('techniques_list', 'Techniques'),
            ('content', 'Instructions'),
            ('cultural_significance', 'Cultural Significance'),
        ],
    },
    'ingredient': {
        'model': Ingredient,
        'label': 'Ingredients',
        'name_field': 'name',
        'fields': [
            ('name', 'Name'),
            ('author_name', 'Author'),
            ('description', 'Description'),
            ('cultural_significance', 'Cultural Significance'),
        ],
    },
    'technique': {
        'model': Technique,
        'label': 'Techniques',
        'name_field': 'name',
        'fields': [
            ('name', 'Name'),
            ('author_name', 'Author'),
            ('regions_list', 'Regions'),
            ('description', 'Description'),
            ('cultural_significance', 'Cultural Significance'),
            ('necessary_tools', 'Necessary Tools'),
        ],
    },
}


def _compare_value(obj, field):
    if field == 'author_name':
        a = obj.author
        return f'{a.first_name} {a.last_name}'.strip() or a.email
    if field == 'regions_list':
        return ', '.join(r.name for r in obj.regions.all()) or '—'
    if field == 'ingredients_list':
        return ', '.join(i.name for i in obj.ingredients.all()) or '—'
    if field == 'techniques_list':
        return ', '.join(t.name for t in obj.techniques.all()) or '—'
    val = getattr(obj, field, '')
    return val if (val or val == 0) else '—'


@login_required
def culinary_compare_page(request):
    kind = request.GET.get('kind', 'recipe')
    if kind not in _COMPARE_KINDS:
        kind = 'recipe'
    spec = _COMPARE_KINDS[kind]
    model = spec['model']

    all_entries = model.objects.select_related('author').prefetch_related('regions').order_by(spec['name_field'])

    raw_ids = request.GET.getlist('ids')
    selected_ids = []
    for v in raw_ids:
        try:
            selected_ids.append(int(v))
        except (TypeError, ValueError):
            continue

    selected_qs = model.objects.filter(pk__in=selected_ids).select_related('author').prefetch_related('regions')
    if kind == 'recipe':
        selected_qs = selected_qs.prefetch_related('ingredients', 'techniques')
    by_id = {o.pk: o for o in selected_qs}
    selected = [by_id[i] for i in selected_ids if i in by_id]

    rows = []
    if len(selected) >= 2:
        for field_key, field_label in spec['fields']:
            rows.append({
                'label': field_label,
                'values': [_compare_value(o, field_key) for o in selected],
            })

    return render(request, 'culinary_compare.html', {
        'kind': kind,
        'kinds': [(k, v['label']) for k, v in _COMPARE_KINDS.items()],
        'all_entries': [(o.pk, getattr(o, spec['name_field'])) for o in all_entries],
        'selected': selected,
        'selected_ids': selected_ids,
        'rows': rows,
        'too_few': 0 < len(selected) < 2,
    })


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
        lat_raw = (request.POST.get('latitude') or '').strip()
        lng_raw = (request.POST.get('longitude') or '').strip()
        ingredient_ids = list(Ingredient.objects.filter(
            pk__in=request.POST.getlist('ingredient_ids')
        ).values_list('pk', flat=True))
        technique_ids = list(Technique.objects.filter(
            pk__in=request.POST.getlist('technique_ids')
        ).values_list('pk', flat=True))
        try:
            latitude = float(lat_raw)
            longitude = float(lng_raw)
            coords_valid = -90 <= latitude <= 90 and -180 <= longitude <= 180
        except ValueError:
            latitude = longitude = None
            coords_valid = False
        if not title or not content or not cultural_significance:
            error = 'Title, instructions and cultural significance are required.'
        elif not coords_valid:
            error = 'Pick a location on the map.'
        else:
            try:
                cook_time_val = max(1, int(cook_time))
            except ValueError:
                cook_time_val = 30
            recipe = Recipe.objects.create(
                author=request.user, title=title, content=content,
                image=image, cook_time=cook_time_val, difficulty=difficulty,
                cultural_significance=cultural_significance,
                latitude=latitude, longitude=longitude,
            )
            recipe.regions.set([profile.sharing_region_id])
            recipe.ingredients.set(ingredient_ids)
            recipe.techniques.set(technique_ids)
            return redirect('/entry/')
    return render(request, 'add_recipe.html', {
        'error': error,
        'all_ingredients': Ingredient.objects.all(),
        'all_techniques': Technique.objects.all(),
    })


@login_required
def recipe_detail_page(request, pk):
    recipe = get_object_or_404(
        Recipe.objects.select_related('author').prefetch_related('regions', 'ingredients', 'techniques'),
        pk=pk,
    )
    return render(request, 'recipe_detail.html', {
        'recipe': recipe,
        'is_liked': recipe.liked_by.filter(pk=request.user.pk).exists(),
        'like_count': recipe.liked_by.count(),
        'comments': _comments_for('recipe', recipe),
        'comment_kind': 'recipe',
        'comment_target_pk': recipe.pk,
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def recipe_like_toggle(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if recipe.liked_by.filter(pk=request.user.pk).exists():
        recipe.liked_by.remove(request.user)
    else:
        recipe.liked_by.add(request.user)
    return redirect(f'/recipes/{recipe.pk}/')


@login_required
def technique_detail_page(request, pk):
    technique = get_object_or_404(
        Technique.objects.select_related('author').prefetch_related('regions'),
        pk=pk,
    )
    return render(request, 'technique_detail.html', {
        'technique': technique,
        'comments': _comments_for('technique', technique),
        'comment_kind': 'technique',
        'comment_target_pk': technique.pk,
    })


@login_required
def search_page(request):
    q = (request.GET.get('q') or '').strip()
    recipes, ingredients, techniques = [], [], []
    if q:
        recipes = (Recipe.objects.filter(
            Q(title__icontains=q) | Q(content__icontains=q)
            | Q(cultural_significance__icontains=q)
        ).select_related('author').prefetch_related('regions').distinct()[:30])
        ingredients = (Ingredient.objects.filter(
            Q(name__icontains=q) | Q(description__icontains=q)
            | Q(cultural_significance__icontains=q)
        ).distinct()[:30])
        techniques = (Technique.objects.filter(
            Q(name__icontains=q) | Q(description__icontains=q)
            | Q(cultural_significance__icontains=q)
        ).distinct()[:30])
    return render(request, 'search.html', {
        'q': q,
        'recipes': recipes,
        'ingredients': ingredients,
        'techniques': techniques,
    })


@login_required
def ingredient_detail_page(request, pk):
    ingredient = get_object_or_404(
        Ingredient.objects.select_related('author'),
        pk=pk,
    )
    return render(request, 'ingredient_detail.html', {
        'ingredient': ingredient,
        'comments': _comments_for('ingredient', ingredient),
        'comment_kind': 'ingredient',
        'comment_target_pk': ingredient.pk,
    })


@login_required
def techniques_page(request):
    g = request.GET
    name = (g.get('name') or '').strip()
    author = (g.get('author') or '').strip()
    region = (g.get('region') or '').strip()
    description = (g.get('description') or '').strip()
    cultural = (g.get('cultural') or '').strip()
    tools = (g.get('tools') or '').strip()

    all_names = list(Technique.objects.values_list('name', flat=True))
    name_corrected = ''
    if name:
        corrected = _fuzzy_match(name, all_names)
        if corrected:
            name_corrected = corrected
    effective_name = name_corrected or name

    qs = Technique.objects.select_related('author').prefetch_related('regions')
    if effective_name:
        qs = qs.filter(name__icontains=effective_name)
    if author:
        qs = qs.filter(Q(author__first_name__icontains=author)
                       | Q(author__last_name__icontains=author)
                       | Q(author__email__icontains=author))
    if region:
        qs = qs.filter(regions__name__icontains=region)
    if description:
        qs = qs.filter(description__icontains=description)
    if cultural:
        qs = qs.filter(cultural_significance__icontains=cultural)
    if tools:
        qs = qs.filter(necessary_tools__icontains=tools)

    qs = qs.distinct()

    filters = {
        'name': name, 'author': author, 'region': region,
        'description': description, 'cultural': cultural, 'tools': tools,
    }
    return render(request, 'techniques.html', {
        'techniques': qs,
        'filters': filters,
        'any_filter': any(filters.values()),
        'all_technique_names': sorted(all_names),
        'name_corrected': name_corrected,
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
        necessary_tools = (request.POST.get('necessary_tools') or '').strip()
        if not name or not description or not cultural_significance:
            error = 'Name, description and cultural significance are required.'
        else:
            technique = Technique.objects.create(
                author=request.user, name=name, description=description,
                cultural_significance=cultural_significance,
                necessary_tools=necessary_tools,
            )
            technique.regions.set([profile.sharing_region_id])
            return redirect('/techniques/')
    return render(request, 'add_technique.html', {
        'error': error,
    })


@login_required
def ingredients_page(request):
    g = request.GET
    name = (g.get('name') or '').strip()
    author = (g.get('author') or '').strip()
    description = (g.get('description') or '').strip()
    cultural = (g.get('cultural') or '').strip()

    all_names = list(Ingredient.objects.values_list('name', flat=True))
    name_corrected = ''
    if name:
        corrected = _fuzzy_match(name, all_names)
        if corrected:
            name_corrected = corrected
    effective_name = name_corrected or name

    qs = Ingredient.objects.select_related('author')
    if effective_name:
        qs = qs.filter(name__icontains=effective_name)
    if author:
        qs = qs.filter(Q(author__first_name__icontains=author)
                       | Q(author__last_name__icontains=author)
                       | Q(author__email__icontains=author))
    if description:
        qs = qs.filter(description__icontains=description)
    if cultural:
        qs = qs.filter(cultural_significance__icontains=cultural)

    qs = qs.distinct()

    filters = {
        'name': name, 'author': author,
        'description': description, 'cultural': cultural,
    }
    return render(request, 'ingredients.html', {
        'ingredients': qs,
        'filters': filters,
        'any_filter': any(filters.values()),
        'all_ingredient_names': sorted(all_names),
        'name_corrected': name_corrected,
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
        if not name or not description:
            error = 'Name and description are required.'
        else:
            Ingredient.objects.create(
                author=request.user, name=name, description=description,
            )
            return redirect('/ingredients/')
    return render(request, 'add_ingredient.html', {
        'error': error,
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def add_comment(request, kind, pk):
    spec = _COMMENT_TARGETS.get(kind)
    if not spec:
        return redirect('/')
    model_cls, field = spec
    target = get_object_or_404(model_cls, pk=pk)
    body = (request.POST.get('body') or '').strip()
    if not body:
        return redirect(f'/{kind}s/{pk}/#comments')
    parent = None
    parent_id = (request.POST.get('parent_id') or '').strip()
    if parent_id:
        parent = Comment.objects.filter(pk=parent_id, parent__isnull=True, **{field: target}).first()
    Comment.objects.create(author=request.user, body=body, parent=parent, **{field: target})
    return redirect(f'/{kind}s/{pk}/#comments')


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def comment_like_toggle(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if comment.liked_by.filter(pk=request.user.pk).exists():
        comment.liked_by.remove(request.user)
    else:
        comment.liked_by.add(request.user)
        comment.disliked_by.remove(request.user)
    return redirect(comment.target_url())


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def comment_dislike_toggle(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if comment.disliked_by.filter(pk=request.user.pk).exists():
        comment.disliked_by.remove(request.user)
    else:
        comment.disliked_by.add(request.user)
        comment.liked_by.remove(request.user)
    return redirect(comment.target_url())


def _coerce_edit_payload(kind, post):
    out = {}
    for field in _EDIT_FIELDS[kind]:
        raw = post.get(field)
        if raw is None:
            continue
        raw = raw.strip()
        if field == 'cook_time':
            try:
                out[field] = max(1, int(raw))
            except (TypeError, ValueError):
                out[field] = 30
        elif field == 'difficulty':
            out[field] = raw if raw in ('Easy', 'Medium', 'Hard') else 'Easy'
        else:
            out[field] = raw
    return out


def _diff_payload(target, payload):
    return {f: v for f, v in payload.items() if getattr(target, f) != v}


@csrf_exempt
@login_required
@require_http_methods(["GET", "POST"])
def edit_entry(request, kind, pk):
    spec = _COMMENT_TARGETS.get(kind)
    if not spec:
        return redirect('/')
    model_cls, _ = spec
    target = get_object_or_404(model_cls, pk=pk)
    is_owner = (target.author_id == request.user.pk)
    error = ''
    info = ''

    if request.method == 'POST':
        for f in _EDIT_FIELDS[kind]:
            if f in _EDIT_OPTIONAL:
                continue
            if not (request.POST.get(f) or '').strip():
                error = f'{_EDIT_LABELS[f]} is required.'
                break
        if not error:
            payload = _coerce_edit_payload(kind, request.POST)
            if is_owner:
                for f, v in payload.items():
                    setattr(target, f, v)
                target.save()
                return redirect(f'/{kind}s/{pk}/')
            else:
                changes = _diff_payload(target, payload)
                if not changes:
                    error = 'No changes to propose.'
                else:
                    note = (request.POST.get('note') or '').strip()
                    EditProposal.objects.create(
                        proposer=request.user, payload=changes,
                        note=note, **{kind: target},
                    )
                    return redirect(f'/{kind}s/{pk}/?proposed=1')

    fields = [{
        'name': f,
        'label': _EDIT_LABELS[f],
        'value': getattr(target, f),
        'optional': f in _EDIT_OPTIONAL,
    } for f in _EDIT_FIELDS[kind]]

    return render(request, 'edit_entry.html', {
        'kind': kind, 'target': target, 'fields': fields,
        'is_owner': is_owner, 'error': error, 'info': info,
        'difficulty_choices': ['Easy', 'Medium', 'Hard'],
    })


@login_required
def proposals_inbox(request):
    incoming = (EditProposal.objects
                .filter(status='pending')
                .filter(Q(recipe__author=request.user)
                        | Q(ingredient__author=request.user)
                        | Q(technique__author=request.user))
                .select_related('proposer', 'recipe', 'ingredient', 'technique'))
    outgoing = (EditProposal.objects
                .filter(proposer=request.user)
                .select_related('recipe', 'ingredient', 'technique')[:30])

    incoming_view = []
    for p in incoming:
        target = p.target
        diff = []
        for field, new_val in p.payload.items():
            diff.append({
                'label': _EDIT_LABELS.get(field, field),
                'old': getattr(target, field),
                'new': new_val,
            })
        incoming_view.append({'p': p, 'diff': diff})

    return render(request, 'proposals_inbox.html', {
        'incoming': incoming_view,
        'outgoing': outgoing,
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def proposal_decide(request, pk):
    proposal = get_object_or_404(
        EditProposal.objects.select_related('recipe', 'ingredient', 'technique'),
        pk=pk,
    )
    target = proposal.target
    if not target or target.author_id != request.user.pk:
        return HttpResponseForbidden('Only the entry owner can decide.')
    if proposal.status != 'pending':
        return redirect('/proposals/')

    decision = (request.POST.get('decision') or '').strip()
    note = (request.POST.get('decision_note') or '').strip()
    if decision == 'approve':
        for field, value in proposal.payload.items():
            setattr(target, field, value)
        target.save()
        proposal.status = 'approved'
    elif decision == 'reject':
        proposal.status = 'rejected'
    else:
        return redirect('/proposals/')

    proposal.decision_note = note
    proposal.decided_at = timezone.now()
    proposal.save()
    return redirect('/proposals/')


@csrf_exempt
@login_required
@require_http_methods(["GET", "POST"])
def submit_report(request, kind, pk):
    spec = _COMMENT_TARGETS.get(kind)
    if not spec:
        return redirect('/')
    model_cls, field = spec
    target = get_object_or_404(model_cls, pk=pk)
    error = ''
    if request.method == 'POST':
        reason = (request.POST.get('reason') or '').strip()
        if not reason:
            error = 'Please describe why you are reporting this entry.'
        else:
            Report.objects.create(reporter=request.user, reason=reason, **{field: target})
            return redirect(f'/{kind}s/{pk}/?reported=1')
    return render(request, 'submit_report.html', {
        'kind': kind, 'target': target, 'error': error,
    })


@login_required
def reports_inbox(request):
    if not request.user.is_staff:
        return HttpResponseForbidden('Admin access only.')
    pending = (Report.objects.filter(status='pending')
               .select_related('reporter', 'recipe__author', 'ingredient__author', 'technique__author'))
    recent = (Report.objects.exclude(status='pending')
              .select_related('reporter', 'resolved_by', 'recipe', 'ingredient', 'technique')[:20])
    return render(request, 'reports_inbox.html', {
        'pending': pending,
        'recent': recent,
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def report_action(request, pk):
    if not request.user.is_staff:
        return HttpResponseForbidden('Admin access only.')
    report = get_object_or_404(
        Report.objects.select_related('recipe__author', 'ingredient__author', 'technique__author'),
        pk=pk,
    )
    if report.status != 'pending':
        return redirect('/reports/')

    action = (request.POST.get('action') or '').strip()
    note = (request.POST.get('resolution_note') or '').strip()
    target = report.target

    if action == 'delete_entry' and target is not None:
        target.delete()
        # Cascade also deletes this report; finalize the (now in-memory) record
        # for the audit trail by re-creating a minimal resolved row.
        Report.objects.create(
            reporter=report.reporter, reason=report.reason,
            status='resolved', resolution_note=note or 'Entry deleted by admin.',
            resolved_by=request.user, resolved_at=timezone.now(),
        )
        return redirect('/reports/')
    elif action == 'ban_user' and target is not None:
        author = target.author
        author.is_active = False
        author.save(update_fields=['is_active'])
        report.status = 'resolved'
        report.resolution_note = note or f'User {author.email} banned.'
    elif action == 'dismiss':
        report.status = 'dismissed'
        report.resolution_note = note
    else:
        return redirect('/reports/')

    report.resolved_by = request.user
    report.resolved_at = timezone.now()
    report.save()
    return redirect('/reports/')
