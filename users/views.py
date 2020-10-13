from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import SignUpForm
from groups.models import Group, GroupMember


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            raw_password = form.cleaned_data.get("password1")
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            if request.GET.get("next", None):
                return redirect(request.GET["next"])
            return redirect("dashboard")
    else:
        form = SignUpForm()
    return render(request, "signup.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                if request.GET.get("next", None):
                    return redirect(request.GET["next"])
                return redirect("dashboard")
    return render(request, "login.html", {"next": request.GET.get("next", None)})


def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def dashboard(request):
    owned_groups = Group.objects.filter(owner=request.user)
    member_groups = (
        GroupMember.objects.select_related("group")
        .filter(user=request.user)
        .exclude(group__owner=request.user)
    )
    return render(
        request,
        "dashboard.html",
        {"owned_groups": owned_groups, "member_groups": member_groups},
    )
