## Checkout

### **POST** `/api/order/checkout/`

Generate a checkout session and shipping options for a transaction request

**Permission:** IsAuthenticated

**Request Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body**
```json
{
    "cart_ids": ["integer"]
}
```

**Response 200 OK:**
```json
{
  "checkout_id": "string",       // Active checkout UUID
  "shipping_options": [
    {
      "name": "string",          // Full courier name (e.g. "J&T Express")
      "code": "string",          // Courier code (e.g. "jnt", "jne")
      "service": "string",       // Service code (e.g. "EZ", "REG", "SDS")
      "description": "string",   // Service name displayed to user
      "cost": "integer",         // Shipping cost in Rupiah
      "etd": "string"            // Estimated arrival (e.g. "1 day")
    }
    // ... other items
  ]
}
```

**Response 401 Unauthorized:**
```json
{
    "detail": "Authentication credentials were not provided."
}
```

**Response 400 Bad Request - invalid data type in body request:**
```json
{
    'detail': 'cart_ids harus berupa list dan tidak boleh kosong.'
}
```

```json
{
    'detail': 'Semua item di dalam cart_ids harus berupa angka (integer).'
}
```

**Response 400 Bad Request - error in Raja Ongkir**
```json
{
    'error': 'Invalid Api key, key not found'
}
```

**Response 400 Bad Request - user not have a shipping address**
```json
{
    'error': 'Alamat pengiriman belum dipilih. Silakan pilih salah satu alamat Anda atau atur salah satu sebagai 'Alamat Utama' (Default).'
}
```

**Response 503 Service Unavailable - nothing data store is active:**
```json
{
    'error': 'Layanan tidak tersedia saat ini.'
}
```

---

## Transaction

### **POST** `/api/order/transaction/`

Generate snap token for frontend to access midtrans payment popup

**Permission:** IsAuthenticated

**Request Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body**
```json
{
    "checkout_id": "string",     
    "code": "string",           // Courier code (e.g. "jnt", "jne")
    "service": "string",        // Service code (e.g. "EZ", "REG", "SDS")
    "cost": "integer"           // Shipping cost in Rupiah
}
```

**Response 200 OK:**
```json
{
    "snap_token": "string"
}
```

**Response 401 Unauthorized:**
```json
{
    "detail": "Authentication credentials were not provided."
}
```

**Response 404 Not Found:**
```json
{
    "detail": "CheckoutSession tidak ditemukan"
}
```

**Response 408 Request Timeout - CheckoutSession has expired:**
```json
{
    "detail": "Sesi telah berakhir atau tidak ditemukan. Silakan ulangi proses (Maks. 10 menit)."
}
```

---

## Comment

### **POST** `/api/comment/`

Generate comment for product reviews from user

**Permission:** IsAuthenticated

**Request Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body**
```json
{
    "rating": "integer",     // min: 1, max: 5
    "content": "string"      // text reviews
}
```

**Response 201 Created:**
```json
{
    'id': 'integer', 
    'product_name': 'string', 
    'username': 'string', 
    'content': 'string', 
    'rating': 'integer', 
    'created_at': 'string', 
    'updated_at': 'string'
}
```

**Response 401 Unauthorized:**
```json
{
    "detail": "Authentication credentials were not provided."
}
```

**Response 404 Not Found:**
```json
{
    "detail": "Product not found"
}
```

**Response 403 Permission Denied - if user not purchase:**
```json
{
    "detail": "User belum pernah membeli product"
}
```

### **PUT** `/api/comment/<int:product_id>/`

Update comment from user

**Permission:** IsAuthenticated

**Request Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body**
```json
{
    "rating": "integer",     // min: 1, max: 5
    "content": "string"      // text reviews
}
```

**Response 200 OK:**
```json
{
    'id': 'integer', 
    'product_name': 'string', 
    'username': 'string', 
    'content': 'string', 
    'rating': 'integer', 
    'created_at': 'string', 
    'updated_at': 'string'
}
```

**Response 401 Unauthorized:**
```json
{
    "detail": "Authentication credentials were not provided."
}
```

**Response 404 Not Found:**
```json
{
    "detail": "Comment not found"
}
```

**Response 403 Permission Denied - if exceeding time limit:**
```json
{
    "detail": "Komentar sudah tidak bisa diedit setelah 24 jam"
}
```
