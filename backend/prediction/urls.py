from django.urls import path
from .views import PredictPriceView, PredictRentView

urlpatterns = [
    path("", PredictPriceView.as_view(), name="predict-price"),
    path("rent/", PredictRentView.as_view(), name="predict-rent"),
]
