# serializers.py
from rest_framework import serializers

class OfficerLoginSerializer(serializers.Serializer):
    NoSiri = serializers.CharField(required=True)
    password = serializers.CharField(required=True)


class OfficerSerializer(serializers.Serializer):
    NoSiri = serializers.CharField(max_length=50)
    Nama = serializers.CharField(max_length=100)
    Bahagian = serializers.CharField(max_length=100)
    Jawatan = serializers.CharField(max_length=100)
    Status = serializers.BooleanField()
    Profile = serializers.CharField(required=False)
    KadKuasa = serializers.CharField(required=False)
    QRCode = serializers.CharField(required=False)
