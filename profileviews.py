# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render
from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .models import Post, LBForumUserProfile

from .forms import ProfileForm
from .models import LBForumUserProfile, Forum

def get_class_by_user(user):
    user_id = user.id
    profile = LBForumUserProfile.objects.get(id=user_id)
    return profile.get_class()

def get_class_by_id(course):
    return Forum.objects.get(id=course)

def profile(request, user_id=None, template_name="lbforum/profile/profile.html"):
    view_user = request.user
    if user_id:
        view_user = get_object_or_404(User, pk=user_id)
    view_only = view_user != request.user
    courses = get_class_by_user(view_user)
    courses = [1,2]
    ext_ctx = {'view_user': view_user, 'view_only': view_only, 'user_courses': courses}
    return render(request, template_name, ext_ctx)

def get_class_by_user(user):
    user_id = user.id
    profile = LBForumUserProfile.objects.get(id=user_id)
    return profile.get_class()
def profile(request, user_id=None, template_name="lbforum/profile/profile.html"):
    view_user = request.user
    if user_id:
        view_user = get_object_or_404(User, pk=user_id)
    view_only = view_user != request.user
    courses = get_class_by_user(view_user)
    print(len(courses))
    ext_ctx = {'view_user': view_user, 'view_only': view_only, 'courses_len': len(courses)}
    return render(request, template_name, ext_ctx)
    
@login_required
def change_profile(request, form_class=ProfileForm, template_name="lbforum/profile/change_profile.html"):
    profile = request.user.lbforum_profile
    if request.method == "POST":
        form = form_class(instance=profile, data=request.POST, files=request.FILES)
        if form.is_valid():
            form.save()
            return redirect('lbforum_profile')
    else:
        form = form_class(instance=profile)
    ext_ctx = {'form': form}
    return render(request, template_name, ext_ctx)


@login_required
def user_topics(request, user_id,
                template_name='lbforum/profile/user_topics.html'):
    view_user = User.objects.get(pk=user_id)
    topics = view_user.topic_set.order_by('-created_on').select_related()
    context = {
        'request': request,
        'topics': topics,
        'view_user': view_user
    }

    return render(request, template_name, context)


@login_required
def user_posts(request, user_id,
               template_name='lbforum/profile/user_posts.html'):
    view_user = User.objects.get(pk=user_id)
    posts = view_user.post_set.order_by('-created_on').select_related()
    context = {
        'request': request,
        'posts': posts,
        'view_user': view_user
    }
    return render(request, template_name, context)

@login_required
def user_courses(request, user_id,
               template_name='lbforum/profile/user_courses.html'):
    view_user = User.objects.get(pk=user_id)
    posts = view_user.post_set.order_by('-created_on').select_related()
    courses = get_class_by_user(view_user)
    context = {
        'request': request,
        'posts': posts,
        'view_user': view_user,
        'courses' : courses
    }
    return render(request, template_name, context)
