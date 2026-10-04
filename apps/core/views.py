from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import SiteSettings
from .serializers import SiteSettingsSerializer


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


class SiteSettingsView(generics.RetrieveAPIView):
    serializer_class = SiteSettingsSerializer

    def get_object(self):
        return SiteSettings.load()
