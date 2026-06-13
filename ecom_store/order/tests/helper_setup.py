from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from shipping_address.models import (City, District, Province, ShippingAddress,
                                     SubDistrict)
from store.models import Store, StoreShippingOption

User = get_user_model()

def set_location_fields():
    province = Province.objects.create(
        ro_id=1, name="NUSA TENGGARA BARAT (NTB)"
    )
    
    city = City.objects.create(ro_id=1, name="MATARAM", province=province)
    
    district = District.objects.create(ro_id=1, name="MATARAM", city=city)
    
    return province, city, district

def set_user():
    user = User.objects.create_user(
        username="test",
        email="test@gmail.com",
        password="test2938484jr",
        phone_number="089384442947",
    )
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    
    return user
    
def set_address(user, province, city, district):
    subdistrict = SubDistrict.objects.create(
        ro_id=1, name="MATARAM TIMUR", zip_code="83121", district=district
    )
    
    shipping_address = ShippingAddress.objects.create(
        province=province,
        city=city,
        district=district,
        subdistrict=subdistrict,
        street_address="Jl. Test",
        is_default=True,
        destination_id=1,
        user=user,
        latitude=-8.5899,
        longitude=116.1107,
    )
    
    return shipping_address
    
def set_store(province, city, district):
    subdistrict_2 = SubDistrict.objects.create(
        ro_id=2, name="PAGESANGAN", zip_code="83127", district=district
    )
    
    # 1. Membuat Superuser
    superuser = User.objects.create_superuser(
        username="admin_test",
        email="admin@example.com",
        password="adminpassword123",
        phone_number="081234567890",
    )

    EmailAddress.objects.create(
        user=superuser, email=superuser.email, verified=True, primary=True
    )

    # 3. Membuat Shipping Address Kedua (untuk superuser)
    shipping_address_2 = ShippingAddress.objects.create(
        province=province,
        city=city,
        district=district,
        subdistrict=subdistrict_2,
        street_address="Jl. Dago No. 123",
        is_default=True,
        destination_id=2,
        user=superuser,
        latitude=-8.6019,
        longitude=116.1033,
    )

    store = Store.objects.create(
        brand_name="Store Test",
        name="Store",
        email="store@gmail.com",
        phone_number="080987654321",
        shipping_address=shipping_address_2,
    )
    
    return store
    
def set_store_shipping_option(store):
    data = []
    for name in ["jne", "jnt", "sicepat"]:
        data.append(StoreShippingOption(
            shipping_name=name,
            store=store
        ))
        
    return StoreShippingOption.objects.bulk_create(data)