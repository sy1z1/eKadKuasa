from django.db import models
#from django.contrib.gis.db import models as gis_models
import datetime

class Admin(models.Model):
    user = models.CharField(max_length=20, primary_key=True)
    pasword = models.CharField(max_length=8)

    def __str__(self):
        return self.user

class Officer(models.Model):
    NoSiri = models.CharField(max_length=4, primary_key=True)
    Password = models.CharField(max_length=8)
    Nama = models.CharField(max_length=255)
    NoKP = models.CharField(max_length=12)
    Bahagian = models.CharField(max_length=255, blank=True, null=True)  # New field
    Jawatan = models.CharField(max_length=255, blank=True, null=True)
    TarikhKeluar = models.DateField(blank=True, null=True, default=datetime.date.today)
    Status = models.BooleanField(default=True)  # Assuming Status is a boolean
    KadKuasa = models.BinaryField(blank=True, null=True)  # For BLOB data

    def __str__(self):
        return self.Nama

class Record(models.Model):
    id = models.AutoField(primary_key=True)
    NoSiri = models.ForeignKey(Officer, on_delete=models.CASCADE, blank=True, null=True)
    tarikh = models.DateField(blank=True, null=True, default=datetime.date.today)
    #location = gis_models.PointField()  # Requires django.contrib.gis

    def __str__(self):
        return f'Record {self.id}'
