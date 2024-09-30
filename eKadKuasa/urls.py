from django.urls import path
from . import views
from .views import OfficerListView

urlpatterns = [
    path("", views.h, name="h"),
    path("login/", views.login, name="login"),
    path("data/", views.data, name="data"),
    path("report/", views.report, name="report"),
    path('personal/<str:no_siri>/', views.personal, name='personal'),
    path("approve/", views.approve, name="approve"),
    path("extend_approve/<str:no_siri>", views.extend_approve, name="extend_approve"),
    path("approve_action/<str:no_siri>", views.approve_action, name="approve_action"),
    path("decline_action/<str:no_siri>", views.decline_action, name="decline_action"),
    path('update/<str:no_siri>/', views.update, name='update'),
    path('officer_login/', views.officer_login, name="officer_login"),
    path('forgot/', views.forgot, name='forgot'),
    path('reset-password/<str:token>/', views.reset_password, name='reset_password'),
    path('user_sign_up/', views.user_sign_up, name='user_sign_up'),
    path('user_data/', views.user_data, name="user_data"),
    path('pdfkadkuasa/', views.pdfkadkuasa, name="pdfkadkuasa"),
    path('user_authorized/', views.user_authorized, name="user_authorized"),
    path('profile_image/<str:no_siri>/', views.profile_image, name='profile_image'),
    path('profile_image_temp/<str:no_siri>/', views.profile_image_temp, name='profile_image_temp'),
    path('api/officers/', OfficerListView.as_view(), name='officer_list_api'),
    path('download_profile_image/<str:no_siri>/', views.download_profile_image, name='download_profile_image'),
    path('download_sign_image/<str:no_siri>/', views.download_sign_image, name='download_sign_image'),
    path('download_images_zip/<str:no_siri>/', views.download_images_zip, name='download_images_zip'),
    path('download_officer_pdf/', views.download_officer_pdf, name='download_officer_pdf'),
    #-----------------API REST--------------------------
    #path('api/officers/', OfficerListView.as_view(), name='officer_list_api'),
    #path('api/officer_login/', views.officer_login, name='officer_login'),
    #path('api/user_sign_up/', views.user_sign_up, name='user_sign_up'),
    #ath('api/user_data/', views.user_data, name='user_data'),  # API endpoint for user data
]

#download_images_zip