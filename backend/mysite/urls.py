"""
URL configuration for mysite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path

from .api_views import analyze_area
from .auth_views import register_user, login_user, google_login

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/analyze-area/", analyze_area, name="analyze_area"),
    path("api/register/", register_user, name="register_user"),
    path("api/login/", login_user, name="login_user"),
    path("api/google-login/", google_login, name="google_login"),
    path("api/predict/", include("prediction.urls")),
]
