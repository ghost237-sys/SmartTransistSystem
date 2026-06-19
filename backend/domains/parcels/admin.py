from django.contrib import admin
from .models import Parcel, ParcelScanEvent

admin.site.register(Parcel)
admin.site.register(ParcelScanEvent)