from django.contrib.auth import logout
from django.shortcuts import render, redirect , get_object_or_404
from django.contrib.auth import login, get_backends
from .forms import CustomUserCreationForm , UserProfileForm
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import UserProfile , FriendRequest, Follow
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse



@login_required
# def home(request):
#     return render(request, "home.html", {})
def home_view(request):
    return render(request, 'home.html')

def custom_logout(request):
    print("Custom logout called")
    logout(request)
    return redirect('login')  # or 'home' or any URL name you want


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


def terms_view(request):
    return render(request, 'registration/Terms.html')  

def privacy_view(request):
    return render(request, 'registration/Privacy.html')







def update_profile(request):
    # If user doesn't have a profile, create one first
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user  # Assign the current user
            profile.save()
            return redirect('base:profile')
    else:
        form = UserProfileForm(instance=profile)

        
    # Get any friend requests sent to the current user
    friend_requests = FriendRequest.objects.filter(to_user=request.user)

    context = {
        'form': form,
        'friend_requests': friend_requests,
        'user': request.user  # current logged-in user
    }

    return render(request, 'profile.html', context)



@login_required
def send_friend_request(request, user_id):
    if request.method == 'POST':
        to_user = get_object_or_404(User, id=user_id)
        FriendRequest.objects.get_or_create(from_user=request.user, to_user=to_user)
    return redirect('base:user_profile', user_id=user_id)


@login_required
def follow_user(request, user_id):
    if request.method == 'POST':
        to_user = get_object_or_404(User, id=user_id)
        Follow.objects.get_or_create(follower=request.user, followed=to_user)
    return redirect('base:user_profile', user_id=user_id)

@login_required
def view_user_profile(request, user_id):
    profile_user = get_object_or_404(User, pk=user_id)
    user_profile = profile_user.userprofile

    current_user = request.user

    # check if current user already sent friend request
    sent_request = FriendRequest.objects.filter(from_user=request.user, to_user=profile_user).exists()
    received_request = FriendRequest.objects.filter(from_user=profile_user, to_user=current_user).exists()

    # Check if users are friends (friend request accepted both ways or accepted once)
    are_friends = FriendRequest.objects.filter(
        (Q(from_user=request.user) & Q(to_user=profile_user) | Q(from_user=profile_user) & Q(to_user=request.user)),
        accepted=True
    ).exists()

    # check if current user already follows this user
    is_following = Follow.objects.filter(follower=current_user, followed=profile_user).exists()

    # Counts for followers, following, and friends
    followers_count = Follow.objects.filter(followed=profile_user).count()
    following_count = Follow.objects.filter(follower=profile_user).count()
    friends_count = FriendRequest.objects.filter(
        (Q(from_user=profile_user) | Q(to_user=profile_user)) & Q(accepted=True)
    ).count()

    context = {
        'user_profile': profile_user,
        'profile': user_profile ,
        'sent_request': sent_request,
        'received_request': True,
        'are_friends': are_friends,
        'is_following': is_following,
        'followers_count': followers_count,
        'following_count': following_count,
        'friends_count': friends_count,
    }
    return render(request, 'user_profile.html', context)




@login_required
def accept_friend_request(request, user_id):
    if request.method == 'POST':
        from_user = get_object_or_404(User, pk=user_id)
        friend_request = get_object_or_404(FriendRequest, from_user=from_user, to_user=request.user)
        friend_request.accepted = True
        friend_request.save()
    return redirect('base:user_profile', user_id=user_id)

@login_required
def reject_friend_request(request, user_id):
    if request.method == 'POST':
        from_user = get_object_or_404(User, pk=user_id)
        friend_request = get_object_or_404(FriendRequest, from_user=from_user, to_user=request.user)
        friend_request.delete()
    return redirect('base:user_profile', user_id=user_id)



# def terms_view(request):
#     return render(request, 'registration/Terms.html')  

