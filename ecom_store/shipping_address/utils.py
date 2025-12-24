# def format_address(shipping_address):
#     street = shipping_address.street_address
#     kecamatan = shipping_address.subdistrict.name
#     kota_kab = shipping_address.city.name
#     kode_pos = shipping_address.subdistrict.zip_code

#     address_parts = [
#         street,
#         f"Kec. {kecamatan}",
#         kota_kab,
#         kode_pos
#     ]
    
#     # Filter jika ada data yang None/Kosong agar tidak muncul koma berlebih
#     return ", ".join([str(p) for p in address_parts if p])