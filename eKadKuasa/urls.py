from django.urls import path, re_path
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .views import OfficerListView
from django.conf.urls import handler404, handler500
from .views import OfficerRecordListView, OfficerRecordDetailView, UserSignUpView, OfficerLoginAPI, OfficerDataView, RecordView

handler404 = 'digitalProject.views.k'
handler500 = 'ekadkuasa.views.p'

urlpatterns = [
    path("", views.login, name="login"),
    re_path(r'^data/?$', views.data, name="data"),
    path("report/", views.report, name="report"),
    path('personal/<str:no_siri>/', views.personal, name='personal'),
    path("approve/", views.approve, name="approve"),
    path("delete/<str:no_siri>/", views.delete_officer, name="delete_officer"),
    path("extend_approve/<str:no_siri>", views.extend_approve, name="extend_approve"),
    path("approve_action/<str:no_siri>", views.approve_action, name="approve_action"),
    path("decline_action/<str:no_siri>", views.decline_action, name="decline_action"),
    path('update/<str:no_siri>/', views.update, name='update'),
    re_path(r'^officer_login/?$', views.officer_login, name="officer_login"),
    path('forgot/', views.forgot, name='forgot'),
    path('reset-password/<str:token>/', views.reset_password, name='reset_password'),
    path('user_sign_up/', views.user_sign_up, name='user_sign_up'),
    path('user_data/', views.user_data, name="user_data"),
    path('user_authorized/<str:no_siri>/', views.user_authorized, name="user_authorized"),
    path('profile_image_temp/<str:no_siri>/', views.profile_image_temp, name='profile_image_temp'),
    path('api/officers/', OfficerListView.as_view(), name='officer_list_api'),
    path('download_profile_image/<str:no_siri>/', views.download_profile_image, name='download_profile_image'),
    path('download_sign_image/<str:no_siri>/', views.download_sign_image, name='download_sign_image'),
    path('download_images_zip/<str:no_siri>/', views.download_images_zip, name='download_images_zip'),
    path('download_officer_pdf/', views.download_officer_pdf, name='download_officer_pdf'),
    path('officer_logout/', views.officer_logout, name='officer_logout'),
    path('err404/', views.h, name='err404'),
    path('error404/', views.d, name='error404'),
    #-----------------API REST--------------------------
    path('api/officer-records/', OfficerRecordListView.as_view(), name='officer_record_list'),
    path('api/officer-records/<str:no_siri>/', OfficerRecordDetailView.as_view(), name='officer_record_detail'),
    path('api/sign-up/', UserSignUpView.as_view(), name='sign_up_api'),
    path('api/login/', OfficerLoginAPI.as_view(), name='login_api'),
    path('api/officer/<str:no_siri>/', OfficerDataView.as_view(), name='officer_data'),
    path('api/recordView/<str:no_siri>/', RecordView.as_view(), name='record_view'),
    #path('api/officers/', OfficerListView.as_view(), name='officer_list_api'),
    #path('api/officer_login/', views.officer_login, name='officer_login'),
    #path('api/user_sign_up/', views.user_sign_up, name='user_sign_up'),
    #ath('api/user_data/', views.user_data, name='user_data'),  # API endpoint for user data
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)