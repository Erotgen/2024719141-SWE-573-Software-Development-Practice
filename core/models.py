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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ingredients')
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    regions = models.ManyToManyField(Region, related_name='ingredients')
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
