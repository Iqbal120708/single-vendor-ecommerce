from celery import shared_task
from django.core.mail import send_mail, EmailMessage
from django.conf import settings

from .models import RefundRequest, Order


@shared_task
def send_refund_status_email(refund_request_id):
    try:
        refund_request = RefundRequest.objects.select_related(
            "order_item", "order_item__product",
            "order_item__order", "order_item__order__user", "order_item__order__store"
        ).get(pk=refund_request_id)
    except RefundRequest.DoesNotExist:
        return  # request sudah dihapus/tidak ada, tidak perlu retry

    order_item = refund_request.order_item
    order = order_item.order
    user = order.user
    product_name = order_item.product.name

    if not user.email:
        return

    subject_map = {
        RefundRequest.Status.APPROVED: "Refund Anda disetujui",
        RefundRequest.Status.REJECTED: "Refund Anda ditolak",
        RefundRequest.Status.COMPLETED: "Refund Anda telah selesai diproses",
    }
    subject = subject_map.get(refund_request.status)
    if not subject:
        return  # status REQUESTED tidak perlu notif ke customer

    message_map = {
        RefundRequest.Status.APPROVED: (
            f"Halo {user.first_name},\n\n"
            f"Refund Anda untuk item {product_name} (Order #{order.order_id}) "
            f"sebesar Rp{refund_request.amount:,} telah disetujui dan sedang diproses.\n\n"
            f"Kami akan mengirim konfirmasi lagi setelah dana selesai dikirim."
        ),
        RefundRequest.Status.REJECTED: (
            f"Halo {user.first_name},\n\n"
            f"Mohon maaf, refund Anda untuk item {product_name} (Order #{order.order_id}) "
            f"tidak dapat kami proses.\n\n"
            f"Jika ada pertanyaan, silakan hubungi kami di {order.store.phone_number}."
        ),
        RefundRequest.Status.COMPLETED: (
            f"Halo {user.first_name},\n\n"
            f"Refund Anda untuk item {product_name} (Order #{order.order_id}) "
            f"sebesar Rp{refund_request.amount:,} telah selesai diproses.\n\n"
            f"Terima kasih atas kesabaran Anda."
        ),
    }
    message = message_map.get(refund_request.status)

    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
        reply_to=[order.store.email],
    )
    email.send()
    
@shared_task
def send_refund_created_email(refund_request_id):
    try:
        refund_request = RefundRequest.objects.select_related(
            "order_item", "order_item__product",
            "order_item__order", "order_item__order__user", "order_item__order__store"
        ).get(pk=refund_request_id)
    except RefundRequest.DoesNotExist:
        return

    order_item = refund_request.order_item
    order = order_item.order
    store = order.store
    product_name = order_item.product.name

    if not store.email:
        return

    subject = f"Permintaan Refund Baru - Order #{order.order_id}"
    message = (
        f"Ada permintaan refund baru yang perlu ditinjau.\n\n"
        f"Order: #{order.order_id}\n"
        f"Item: {product_name}\n"
        f"Nominal: Rp{refund_request.amount:,}\n"
        f"Alasan: {refund_request.get_reason_display()}\n"
        f"Catatan customer: {refund_request.note or '-'}\n\n"
        f"Silakan tinjau di halaman admin."
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[store.email],
    )
    
@shared_task
def send_refund_anomaly_email(order_id, refund_request_id):
    try:
        order = Order.objects.select_related("store").get(pk=order_id)
    except Order.DoesNotExist:
        return

    if not order.store.email:
        return

    send_mail(
        subject=f"[URGENT] Anomali Order #{order.order_id} - Refund Terblokir",
        message=(
            f"Order #{order.order_id} berstatus PAID tapi stock belum diproses "
            f"(reduce_stock kemungkinan gagal). Refund request #{refund_request_id} "
            f"tidak bisa diproses sampai anomali ini diperiksa manual."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.store.email],
    )