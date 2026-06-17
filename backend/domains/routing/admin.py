from django.contrib import admin
from .models import Route, Stop, Trip

admin.site.register(Route)
admin.site.register(Stop)
admin.site.register(Trip)