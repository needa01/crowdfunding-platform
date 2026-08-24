import uuid

from django.db import models
from django.conf import settings
from django_enum.fields import EnumField

from crowdfunding.enums import KYC_Status, NGOType, Status

class NGOProfile(models.Model):

    

    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ngo_profile"
    )

    ngo_name = models.CharField(
        max_length=255
    )

    ngo_type = EnumField(
        NGOType
    )

    reg_num = models.CharField(
        max_length=100,
        unique=True
    )



    contact_person_name = models.CharField(
        max_length=255
    )

    contact_person_designation = models.CharField(
        max_length=255
    )
    
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)
    
    website = models.URLField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        db_table = "ngo_profile"
        verbose_name = "NGO Profile"
        verbose_name_plural = "NGO Profiles"

    def __str__(self):
        return self.ngo_name
    
    
    
    
class CSRProfile(models.Model):


    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="csr_profile"
    )
    csr_name = models.CharField(
        max_length=255
    )
    csr_reg_num = models.CharField(
        max_length=100,
        unique=True
    )
    
    contact_person_name = models.CharField(
        max_length=255
    )
    contact_person_designation = models.CharField(
        max_length=255
    )

    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)
    
    
    website = models.URLField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        db_table = "csr_profile"
        verbose_name = "CSR Profile"
        verbose_name_plural = "CSR Profiles"

    def __str__(self):
        return self.csr_name
    
    