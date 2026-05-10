from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


class Region(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Profile(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('prefer_not', 'Prefer not to say'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    date_of_birth = models.DateField(blank=True, null=True)
    profile_photo = models.FileField(upload_to='profiles/', blank=True, null=True)
    description = models.TextField(blank=True, default='')
    sharing_region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name='members', blank=True, null=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True, default='')

    def is_complete(self):
        return bool(
            self.sharing_region_id and self.description
            and self.date_of_birth and self.gender
        )

    def save(self, *args, **kwargs):
        if self.pk:
            old_region_id = Profile.objects.filter(pk=self.pk).values_list('sharing_region_id', flat=True).first()
            if old_region_id is not None and old_region_id != self.sharing_region_id:
                raise ValidationError("Sharing region cannot be changed after registration (FR-4).")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} ({self.sharing_region.name})"


class Technique(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='techniques')
    name = models.CharField(max_length=120)
    description = models.TextField()
    regions = models.ManyToManyField(Region, related_name='techniques')
    cultural_significance = models.TextField(blank=True, default='')
    necessary_tools = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ingredients')
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    cultural_significance = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Recipe(models.Model):
    DIFFICULTY_CHOICES = [('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recipes')
    title = models.CharField(max_length=200)
    content = models.TextField()
    regions = models.ManyToManyField(Region, related_name='recipes')
    ingredients = models.ManyToManyField(Ingredient, blank=True, related_name='recipes')
    techniques = models.ManyToManyField(Technique, blank=True, related_name='recipes')
    image = models.FileField(upload_to='recipes/', blank=True, null=True)
    cook_time = models.PositiveIntegerField(help_text="Minutes", default=30)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='Easy')
    cultural_significance = models.TextField(blank=True, default='')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    liked_by = models.ManyToManyField(User, related_name='liked_recipes', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Comment(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    body = models.TextField()
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, null=True, blank=True, related_name='comments')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, null=True, blank=True, related_name='comments')
    technique = models.ForeignKey(Technique, on_delete=models.CASCADE, null=True, blank=True, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    liked_by = models.ManyToManyField(User, related_name='liked_comments', blank=True)
    disliked_by = models.ManyToManyField(User, related_name='disliked_comments', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def target_url(self):
        if self.recipe_id:
            return f'/recipes/{self.recipe_id}/#comments'
        if self.ingredient_id:
            return f'/ingredients/{self.ingredient_id}/#comments'
        if self.technique_id:
            return f'/techniques/{self.technique_id}/#comments'
        return '/'


class EditProposal(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    proposer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='edit_proposals')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, null=True, blank=True, related_name='edit_proposals')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, null=True, blank=True, related_name='edit_proposals')
    technique = models.ForeignKey(Technique, on_delete=models.CASCADE, null=True, blank=True, related_name='edit_proposals')
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    note = models.TextField(blank=True, default='')
    decision_note = models.TextField(blank=True, default='')
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def target(self):
        return self.recipe or self.ingredient or self.technique

    @property
    def kind(self):
        if self.recipe_id: return 'recipe'
        if self.ingredient_id: return 'ingredient'
        if self.technique_id: return 'technique'
        return ''

    def target_detail_url(self):
        kind = self.kind
        target = self.target
        if not kind or not target: return '/'
        return f'/{kind}s/{target.pk}/'


class Report(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_made')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    technique = models.ForeignKey(Technique, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    resolution_note = models.TextField(blank=True, default='')
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports_resolved')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def target(self):
        return self.recipe or self.ingredient or self.technique

    @property
    def kind(self):
        if self.recipe_id: return 'recipe'
        if self.ingredient_id: return 'ingredient'
        if self.technique_id: return 'technique'
        return ''
