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
from .views import authView 
from .views import home_view , update_profile 
from django.contrib.auth.views import LogoutView

app_name = 'base' 

urlpatterns = [ 
     path('', home_view, name='home'),
    path("accounts/signup/", authView, name="authView"),  # Changed from "signup/" to "accounts/signup/"
    # path('signup/', authView, name='signup'),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path('profile/', update_profile, name='profile'),


]



