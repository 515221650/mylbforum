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



def get_class_by_id(course):
    return Forum.objects.get(id=course)

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
}

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
    is_my_profile = view_user == request.user 
    profile = LBForumUserProfile.objects.get(id=user_id)
    like_classes_id = profile.get_like_classes()
    taken_classes_id = profile.get_taken_classes()

    print("like_classes_id : " , like_classes_id)
    print("taken_classes_id : " , taken_classes_id)

    like_classes = []
    taken_classes = []
    for course in like_classes_id:
        like_classes.append(get_class_by_id(course))

    #for course in like_classes_id:
    #    print(course.__str__())

    for course in taken_classes_id:
        taken_classes.append(get_class_by_id(course))

    my_id = request.user.id
    my_profile = LBForumUserProfile.objects.get(id=my_id)
    my_like_classes_id = my_profile.get_like_classes()
    my_taken_classes_id = my_profile.get_taken_classes()

    like_common = []
    taken_common = []

    for course in my_like_classes_id:
        if (not is_my_profile) and (course in like_classes_id):
            like_common.append(True)
        else:
            like_common.append(False)

    for course in my_taken_classes_id:
        if (not is_my_profile) and (course in taken_classes_id):
            taken_common.append(True)
        else:
            taken_common.append(False)


    context = {
        'request': request,
        'posts': posts,
        'view_user': view_user,
        'courses' : courses,
        'like_classes' : list(zip(like_classes, like_common)),
        'taken_classes' : list(zip(taken_classes, taken_common))
    }
    return render(request, template_name, context)
