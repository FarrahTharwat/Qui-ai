#from django.urls import path, include
#from .views import authView, home 
#from django.contrib.auth.views import LogoutView

#urlpatterns = [
 #path("", home, name="home"), 
# path("signup/", authView, name="authView"),  
# path("accounts/", include("django.contrib.auth.urls")),
# path("accounts/logout/", LogoutView.as_view(), name="logout"),  # Explicitly defining logout


#]
from django.urls import path, include
# from .views import authView 
# from .views import home_view , update_profile ,send_friend_request, follow_user , view_user_profile
# from django.contrib.auth.views import LogoutView
from .views import (
    authView,
    home_view,
    update_profile,
    send_friend_request,
    follow_user,
    view_user_profile,
    accept_friend_request,
    reject_friend_request,
    custom_logout,
)
# from . import views

app_name = 'base' 

urlpatterns = [ 
    path('', home_view, name='home'),
    path("accounts/signup/", authView, name="authView"),  # Changed from "signup/" to "accounts/signup/"
    path("accounts/", include("django.contrib.auth.urls")),
    # path("accounts/logout/", LogoutView.as_view(next_page='home'), name="logout"),
    path('accounts/logout/', custom_logout, name='logout'),
    path('profile/', update_profile, name='profile'),
    path('send_friend_request/<int:user_id>/', send_friend_request, name='send_friend_request'),
    path('profile/<int:user_id>/', view_user_profile, name='user_profile'),
    path('follow/<int:user_id>/', follow_user, name='follow_user'),
    path('accept-friend-request/<int:request_id>/', accept_friend_request, name='accept_friend_request'),
    path('reject-friend-request/<int:request_id>/', reject_friend_request, name='reject_friend_request'),


]



