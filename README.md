# ecommerce
Single Vendor E-Commerce API project about admin who manages the product and order, user only buy the product, manage the cart, track order status and others. This project is integrated with RajaOngkir and Midtrans

# Technologies
- languange: python 3.12
- framework: Django 5 and DjangoRestFramework
- database: MySql

# Features
- Authentication and Authorization
- manage the shipping address
- manage the Product for admin
- manage the Order for admin
- manage the Cart
- only read product for user
- track order status 
- Read order
- shipping API with RajaOngkir 
- payment gateway with midtrans
- Checkout
- comment the product

# How to run
- clone the repo
```
https://github.com/Iqbal120708/single-vendor-ecommerce/
cd single-vendor-ecommerce
```
- create and activate a virtual environment
- add virtual environment variables. open the script `settings.py` to know what the variables are 
- install python libraries and frameworks
```
pip install -r requirements.txt
```
- add your database configuration in `settings.py` or in variable virtual enviroment
- migrate the model
```
python manage.py makemigrations
python manage.py migrate
```
- activate the server
```
cd ecom_store
python manage.py runserver
```
