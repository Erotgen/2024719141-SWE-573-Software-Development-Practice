from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from view import (
    add_ingredient_page,
    add_recipe_page,
    add_technique_page,
    culinary_data_page,
    culinary_road_page,
    entry_page,
    index,
    ingredient_detail_page,
    ingredients_page,
    login_page,
    logout_view,
    profile_page,
    recipe_detail_page,
    recipes_page,
    register_page,
    technique_detail_page,
    techniques_page,
)

urlpatterns = [
    path('', index),
    path('login/', login_page),
    path('logout/', logout_view),
    path('register/', register_page),
    path('entry/', entry_page),
    path('culinary-road/', culinary_road_page),
    path('culinary-data/', culinary_data_page),
    path('profile/', profile_page),
    path('recipes/', recipes_page),
    path('recipes/add/', add_recipe_page),
    path('recipes/<int:pk>/', recipe_detail_page),
    path('techniques/', techniques_page),
    path('techniques/add/', add_technique_page),
    path('techniques/<int:pk>/', technique_detail_page),
    path('ingredients/', ingredients_page),
    path('ingredients/add/', add_ingredient_page),
    path('ingredients/<int:pk>/', ingredient_detail_page),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
