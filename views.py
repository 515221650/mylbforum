# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldError
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
# from django.contrib import messages
from lbutils import get_client_ip

from .templatetags.lbforum_filters import topic_can_post
from .forms import EditPostForm, NewPostForm, ForumForm
from .models import Topic, Forum, Post, LBForumUserProfile, TopicType

User = get_user_model()

def build_dic(friends):
    new_friends = [{"userid":i, "username":LBForumUserProfile.objects.get(id=i).nickname} for i in friends]
    return new_friends

def get_all_topics(user, select_related=True):
    topics = Topic.objects.all()
    if not (user.has_perm('lbforum.sft_mgr_forum')):
        qparam = Q(hidden=False)
        if user.is_authenticated:
            qparam = qparam | Q(forum__admins=user) | Q(posted_by=user)
        qparam = Q(is_chat=False) & qparam
        topics = topics.filter(qparam)
    if select_related:
        topics = topics.select_related(
            'posted_by__lbforum_profile',
            'last_post__last_updated_by__lbforum_profile',
            'forum'
        )
    return topics.distinct()


def get_all_posts(user, select_related=True):
    qs = Post.objects.all()
    if not (user.has_perm('lbforum.sft_mgr_forum')):
        qparam = Q(topic__hidden=False)
        if user.is_authenticated:
            qparam = qparam | Q(topic__forum__admins=user) | Q(posted_by=user)
        qs = qs.filter(qparam)
    if select_related:
        qs = qs.select_related(
            'posted_by', 'posted_by__lbforum_profile',
        )
    return qs.distinct()


def index(request, template_name="lbforum/index.html"):
    ctx = {}
    topics = None
    user = request.user
    topics = get_all_topics(user)
    topics = topics.order_by('-last_reply_on')[:20]
    ctx['topics'] = topics
    return render(request, template_name, ctx)


def recent(request, template_name="lbforum/recent.html"):
    ctx = {}
    user = request.user
    topics = get_all_topics(user)
    q = request.GET.get('q', '')
    if q:
        topics = topics.filter(subject__icontains=q)
    ctx['q'] = q
    ctx['topics'] = topics.order_by('-last_reply_on')
    ctx['request'] = request
    return render(request, template_name, ctx)


def forum(
        request, forum_slug, topic_type='', topic_type2='',
        template_name="lbforum/forum.html"):

    forum = get_object_or_404(Forum, slug=forum_slug)
    user = request.user
    topics = get_all_topics(user)
    topics = topics.filter(forum=forum)
    if topic_type and topic_type != 'good':
        topic_type2 = topic_type
        topic_type = ''
    if topic_type == 'good':
        topics = topics.filter(level__gt=30)
    if topic_type2:
        topics = topics.filter(topic_type__slug=topic_type2)

    order_by = request.GET.get('order_by', '-last_reply_on')

    try:
        topics = topics.order_by('-sticky', order_by)
    except FieldError:
        topics = topics.order_by('-sticky', '-last_reply_on')

    form = ForumForm(request.GET)
    userid = user.id
    profile = LBForumUserProfile.objects.get(id=userid)
    friends = profile.get_friend()
    print('friends:')
    print(friends)
    if request.method == "POST":
        keyword = request.POST.get('stat')
        if keyword is not None:
            old = profile.change_class(forum.id, keyword)
            forum.change(userid, old, keyword)

    users_like = forum.get_users_like()
    users_taken = forum.get_users_taken()
    friends_like = []
    friends_taken = []
    for i in friends:
        if int(i) in users_like:
            profile = LBForumUserProfile.objects.get(id=int(i))
            friends_like.append({ 'username': profile.__str__(), 'userid':profile.id})
        if int(i) in users_taken:
            profile = LBForumUserProfile.objects.get(id=int(i))
            friends_like.append({ 'username': profile.__str__(), 'userid':profile.id})
    print('friends_taken:')
    print(friends_taken)
    friends = build_dic(friends)
    choose = 0
    if forum.id in profile.get_like_classes():
        choose = 1
    if forum.id in profile.get_taken_classes():
        choose = 2

    ext_ctx = {
        'request': request,
        'form': form, 'forum': forum, 'topics': topics,
        'topic_type': topic_type, 'topic_type2': topic_type2,
        'friends_like': friends_like,
        'friends_taken': friends_taken,
        'choose':choose,
        'slug':forum_slug,
        'avg_rating': "{:.2f}".format(forum.stars)
    }
    return render(request, template_name, ext_ctx)

def rating(request):
    slug = request.POST.get('slug')
    if request.POST.get('rate') is not None:
        theforum = get_object_or_404(Forum, slug=slug)
        theforum.do_star(int(request.POST.get('rate')))
    return forum(request, slug)

def topic(request, topic_id, template_name="lbforum/topic.html"):
    user = request.user
    topic = get_object_or_404(Topic, pk=topic_id)
    if topic.hidden and not topic.forum.is_admin(user):
        return HttpResponse(ugettext('no right'))
    topic.num_views += 1
    topic.save()
    posts = get_all_posts(user)
    posts = posts.filter(topic=topic)
    posts = posts.filter(topic_post=False)
    posts = posts.order_by('created_on')
    ext_ctx = {
        'request': request,
        'topic': topic,
        'posts': posts,
        'has_replied': topic.has_replied(request.user),
        'can_admin': topic.forum.is_admin(user)
    }
    return render(request, template_name, ext_ctx)


def chat(request, topic_id, template_name="lbforum/chat.html"):
    # print(topic_id)
    # print("THISISTOPIC")
    user = request.user
    topic = get_object_or_404(Topic, pk=topic_id)
    if topic.hidden and not topic.forum.is_admin(user):
        return HttpResponse(ugettext('no right'))
    topic.num_views += 1
    topic.save()
    obj = topic.owns1
    if topic.owns1 == user.id:
        obj = topic.owns2
    obj = User.objects.get(id=obj)
    posts = get_all_posts(user)
    posts = posts.filter(topic=topic)
    posts = posts.filter(topic_post=False)
    posts = posts.order_by('created_on')
    ext_ctx = {
        'request': request,
        'topic': topic,
        'posts': posts,
        'has_replied': topic.has_replied(request.user),
        'can_admin': topic.forum.is_admin(user),
        'userobj': obj
    }
    return render(request, template_name, ext_ctx)


def post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    return HttpResponseRedirect(post.get_absolute_url_ext())


@csrf_exempt
def markitup_preview(request, template_name="lbforum/markitup_preview.html"):
    return render(request, template_name, {'message': request.POST['data']})


@login_required
def new_post(
        request, forum_id=None, topic_id=None, form_class=NewPostForm,
        template_name='lbforum/post.html'):
    tags = TopicType.objects.all()
    user = request.user
    if not user.lbforum_profile.nickname:
        return redirect('lbforum_change_profile')
    qpost = topic = forum = first_post = preview = None
    post_type = _('topic')
    topic_post = True
    initial = {}

    print("#######")
    if forum_id:
        forum = get_object_or_404(Forum, pk=forum_id)
    if topic_id:
        print(topic_id)
        print("ASDASD")
        post_type = _('reply')
        topic_post = False
        topic = get_object_or_404(Topic, pk=topic_id)
        if not topic_can_post(topic, user):
            return HttpResponse(_("you can't reply, this topic closed."))
        forum = topic.forum
        first_post = topic.posts.order_by('created_on').first()

    initial['forum'] = forum

    print("!!!!!!")
    if request.method == "POST":
        tag = request.POST["tag"]
        form = form_class(
            request.POST, user=user, forum=forum,
            initial=initial,
            topic=topic, ip=get_client_ip(request))
        preview = request.POST.get('preview', '')
        if form.is_valid() and request.POST.get('submit', ''):
            post = form.save(tag)
            forum = post.topic.forum
            if topic:
                return HttpResponseRedirect(post.get_absolute_url_ext())
            else:
                return HttpResponseRedirect(reverse("lbforum_forum",
                                                    args=[forum.slug]))
    else:
        qid = request.GET.get('qid', '')
        if qid:
            qpost = get_object_or_404(Post, id=qid)
            initial['message'] = "[quote=%s]%s[/quote]" % (
                qpost.posted_by.lbforum_profile, qpost.message)
        form = form_class(initial=initial, forum=forum)

    print("@@@@@@")
    print(tags)
    taglist = []
    for i in tags:
        if not(i.__str__() == "test"):
            taglist.append(i.__str__())
    ext_ctx = {
        'forum': forum,
        'show_forum_field': topic_post,
        'form': form,
        'topic': topic,
        'first_post': first_post,
        'post_type': post_type,
        'preview': preview,
        'tags': taglist
    }
    ext_ctx['attachments'] = user.lbattachment_set.filter(
        pk__in=request.POST.getlist('attachments'))
    ext_ctx['is_new_post'] = True
    ext_ctx['topic_post'] = topic_post
    return render(request, template_name, ext_ctx)


@login_required
def new_chat_post2(
        request, user_id=None, form_class=NewPostForm,
        template_name='lbforum/post.html'):
    return new_chat_post(request,user_id=user_id)
@login_required
def new_chat_post3(
        request, topic_id=None, form_class=NewPostForm,
        template_name='lbforum/post.html'):
    return new_chat_post(request, topic_id=topic_id)

def new_chat_post(
        request, user_id=None, forum_id=None, topic_id=None, form_class=NewPostForm,
        template_name='lbforum/post.html'):

    user = request.user

    if user_id:
        profile = LBForumUserProfile.objects.get(id=user.id)
        chat_list = profile.get_chat_list()
        print(chat_list)
        print(user_id)
        print(type(user_id))
        if user_id in chat_list.keys():
            return HttpResponseRedirect(reverse("lbforum_chat",
                                         args=[chat_list[user_id]]))

    if not user.lbforum_profile.nickname:
        return redirect('lbforum_change_profile')
    qpost = topic = forum = first_post = preview = None
    post_type = _('topic')
    topic_post = True
    initial = {}
    forum = Forum.objects.get(id=1)
    if forum_id:
        forum = get_object_or_404(Forum, pk=forum_id)
    if topic_id:
        print(topic_id)
        print("ASDASD")
        post_type = _('reply')
        topic_post = False
        topic = get_object_or_404(Topic, pk=topic_id)
        if not topic_can_post(topic, user):
            return HttpResponse(_("you can't reply, this topic closed."))
        forum = topic.forum
        first_post = topic.posts.order_by('created_on').first()
    initial['forum'] = forum
    if request.method == "POST":
        form = form_class(
            request.POST, user=user, forum=forum,
            initial=initial,
            topic=topic, ip=get_client_ip(request))
        preview = request.POST.get('preview', '')
        print(form.is_bound)
        print(form.errors)
        print(form.is_valid())
        print("asdasd")
        if form.is_valid() and request.POST.get('submit', ''):
            post = form.save()
            forum = post.topic.forum
            if topic:
                return HttpResponseRedirect(post.get_absolute_url_ext().replace("topic", "chat"))
            else:
                return HttpResponseRedirect(reverse("lbforum_forum",
                                                    args=[forum.slug]))
    else:
        topic = Topic(forum=forum,
                      posted_by=user,
                      subject="chat",
                      need_replay=False,
                      need_reply_attachments=False,
                      topic_type=TopicType.objects.get(name="test"),
                      owns1=user_id,
                      owns2=user.id,
                      is_chat = True
                      )
        topic_post = True
        topic.save()
        profile1 = LBForumUserProfile.objects.get(id=user.id)
        profile2 = LBForumUserProfile.objects.get(id=user_id)
        profile1.add_chat(user_id, topic.id)
        profile2.add_chat(user.id, topic.id)
        posts = get_all_posts(user)
        posts = posts.filter(topic=topic)
        posts = posts.filter(topic_post=False)
        posts = posts.order_by('created_on')
        ext_ctx = {
            'request': request,
            'topic': topic,
            'posts': posts,
            'has_replied': topic.has_replied(request.user),
            'can_admin': topic.forum.is_admin(user)
        }
        return HttpResponseRedirect(reverse("lbforum_chat", args=[topic.id]))



@login_required
def edit_post(request, post_id, form_class=EditPostForm,
              template_name="lbforum/post.html"):
    preview = None
    post_type = _('reply')
    edit_post = get_object_or_404(Post, id=post_id)
    if not (request.user.is_staff or request.user == edit_post.posted_by):
        return HttpResponse(ugettext('no right'))
    if edit_post.topic_post:
        post_type = _('topic')
    if request.method == "POST":
        form = form_class(instance=edit_post, user=request.user,
                          data=request.POST)
        preview = request.POST.get('preview', '')
        if form.is_valid() and request.POST.get('submit', ''):
            edit_post = form.save()
            return HttpResponseRedirect('../')
    else:
        form = form_class(instance=edit_post)
    ext_ctx = {
        'form': form,
        'post': edit_post,
        'topic': edit_post.topic,
        'forum': edit_post.topic.forum,
        'post_type': post_type,
        'preview': preview,
        'attachments': edit_post.attachments.all()
    }
    # ext_ctx['unpublished_attachments'] = request.user.lbattachment_set.filter(activated=False)
    ext_ctx['topic_post'] = edit_post.topic_post
    return render(request, template_name, ext_ctx)


@login_required
def delete_topic(request, topic_id):
    if not request.user.is_staff:
        # messages.error(_('no right'))
        return HttpResponse(ugettext('no right'))
    topic = get_object_or_404(Topic, id=topic_id)
    forum = topic.forum
    topic.delete()
    forum.update_state_info()
    return HttpResponseRedirect(reverse("lbforum_forum", args=[forum.slug]))


@login_required
def delete_post(request, post_id):
    if not request.user.is_staff:
        return HttpResponse(ugettext('no right'))
    post = get_object_or_404(Post, id=post_id)
    topic = post.topic
    post.delete()
    topic.update_state_info()
    topic.forum.update_state_info()
    # return HttpResponseRedirect(request.path)
    return HttpResponseRedirect(reverse("lbforum_topic", args=[topic.id]))


@login_required
def toggle_topic_attr(request, topic_id, attr):
    topic = get_object_or_404(Topic, id=topic_id)
    forum = topic.forum
    if not forum.is_admin(request.user):
        return HttpResponse(ugettext('no right'))
    if attr == 'sticky':
        topic.sticky = not topic.sticky
    elif attr == 'close':
        topic.closed = not topic.closed
    elif attr == 'hide':
        topic.hidden = not topic.hidden
    elif attr == 'distillate':
        topic.level = 30 if topic.level >= 60 else 60
    topic.save()
    return HttpResponseRedirect(reverse("lbforum_topic", args=[topic.id]))
