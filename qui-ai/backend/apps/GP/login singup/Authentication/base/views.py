# from django.shortcuts import render
# from django.contrib.auth.forms import UserCreationForm
# from django.contrib.auth.decorators import login_required


# @login_required
# def home(request):
#  return render(request, "home.html", {})  

# def authView(request):
#  if request.method =="POST":
#   form = UserCreationForm(request.POST or None)
#   if form.is_valid():
#    form.save()
#  else:
#   form = UserCreationForm()
#  return render(request, "registration/signup.html", {"form": form})

from django.shortcuts import render, redirect
from django.contrib.auth import login, get_backends
from .forms import CustomUserCreationForm , UserProfileForm
from django.contrib.auth.decorators import login_required
from .models import UserProfile


@login_required
# def home(request):
#     return render(request, "home.html", {})
def home_view(request):
    return render(request, 'home.html')


def authView(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Get the first backend
            backend = get_backends()[0]
            # Set the backend for the user
            user.backend = f"{backend.__module__}.{backend.__class__.__name__}"
            login(request, user)
            return redirect('base:home')  # Redirect to home page after login
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/signup.html", {"form": form})



# def update_profile(request):
#     profile = UserProfile.objects.get(user=request.user)
#     if request.method == 'POST':
#         form = UserProfileForm(request.POST, request.FILES, instance=profile)
#         if form.is_valid():
#             form.save()
#             return redirect('profile')
#     else:
#         form = UserProfileForm(instance=profile)
    
#     return render(request, 'update_profile.html', {'form': form})
def update_profile(request):
    # If user doesn't have a profile, create one first
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user  # Assign the current user
            profile.save()
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)

    return render(request, 'base/profile.html', {'form': form})

