from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from api import admin_views, ai_views, media_views, views


urlpatterns = [
    path("healthz", views.health),
    path("api/v1/csrf", views.csrf_cookie),
    path("api/v1/access", views.customer_access),
    path("api/v1/outlets/<uuid:outlet_id>/config", views.outlet_config),
    path("api/v1/outlets/<uuid:outlet_id>/menu", views.outlet_menu),
    path("q/<str:token>", views.qr_bootstrap),
    path("api/v1/orders", views.orders),
    path("api/v1/orders/<uuid:order_id>", views.order_detail),
    path("api/v1/service-requests", views.service_requests),
    path("api/v1/staff/login", views.staff_login),
    path("api/v1/staff/logout", views.staff_logout),
    path("api/v1/staff/me", views.staff_me),
    path("api/v1/staff/outlets", views.staff_outlets),
    path("api/v1/staff/outlets/<uuid:outlet_id>/tables", views.staff_tables),
    path("api/v1/staff/outlets/<uuid:outlet_id>/catalogue", views.staff_catalogue),
    path("api/v1/staff/outlets/<uuid:outlet_id>/description-draft", ai_views.description_draft),
    path("api/v1/staff/outlets/<uuid:outlet_id>/quick-items", admin_views.quick_item_create),
    path("api/v1/staff/outlets/<uuid:outlet_id>/queue", views.staff_queue),
    path("api/v1/staff/outlets/<uuid:outlet_id>/service-requests", views.staff_requests),
    path("api/v1/staff/visits/<uuid:visit_id>/orders", views.staff_visit_orders),
    path("api/v1/staff/orders/<uuid:order_id>/seen", views.staff_order_seen),
    path("api/v1/staff/service-requests/<uuid:request_id>/resolve", views.staff_resolve_request),
    path("api/v1/staff/lines/<uuid:line_id>/progress", views.staff_line_progress),
    path("api/v1/staff/visits/<uuid:visit_id>/checkout", views.staff_checkout),
    path("api/v1/staff/visits/<uuid:visit_id>/cancel-checkout", views.staff_cancel_checkout),
    path("api/v1/staff/visits/<uuid:visit_id>/complete-billing", views.staff_complete_billing),
    path("api/v1/staff/outlets/<uuid:outlet_id>/events", views.staff_events),
    path("api/v1/staff/outlets/<uuid:outlet_id>/events/stream", views.staff_event_stream),
    path("api/v1/staff/brands/<uuid:brand_id>", admin_views.brand_update),
    path("api/v1/staff/outlets/<uuid:outlet_id>/branding", admin_views.outlet_brand_update),
    path("api/v1/staff/outlets/<uuid:outlet_id>/ordering", admin_views.outlet_ordering_update),
    path("api/v1/staff/brands/<uuid:brand_id>/categories", admin_views.category_create),
    path("api/v1/staff/brands/<uuid:brand_id>/items", admin_views.item_create),
    path("api/v1/staff/items/<uuid:item_id>/images", media_views.item_images),
    path("api/v1/staff/items/<uuid:item_id>/images/<uuid:image_id>", media_views.item_image_remove),
    path("api/v1/staff/items/<uuid:item_id>/variants", admin_views.variant_create),
    path("api/v1/staff/variants/<uuid:variant_id>/modifier-groups", admin_views.modifier_group_create),
    path("api/v1/staff/modifier-groups/<uuid:group_id>/options", admin_views.modifier_option_create),
    path("api/v1/staff/outlets/<uuid:outlet_id>/modifiers", admin_views.outlet_modifier_create),
    path("api/v1/staff/outlets/<uuid:outlet_id>/offerings", admin_views.offering_create),
    path("api/v1/staff/outlets/<uuid:outlet_id>/offerings/<uuid:offering_id>", admin_views.offering_update),
    path("api/v1/staff/tables/<uuid:table_id>/rotate-qr", admin_views.table_rotate_qr),
]

if settings.DEBUG:
    urlpatterns += static("/uploads/", document_root=settings.MEDIA_ROOT)
