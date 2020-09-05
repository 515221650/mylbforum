# -*- coding: UTF-8 -*-
from __future__ import unicode_literals

import json

from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from easy_thumbnails.fields import ThumbnailerImageField
from easy_thumbnails.files import get_thumbnailer
from el_pagination import settings as elp_setttings
from django.utils.encoding import python_2_unicode_compatible

from lbattachment.models import LBAttachment


def get_people_example():
    friend1 = {"userid":1, "username":111}
    friend2 = {"userid":2, "username": 222}
    k = json.dumps([friend1, friend2])
    return k


@python_2_unicode_compatible
class Category(models.Model):
    name = models.CharField(max_length=100)
    descn = models.TextField(blank=True)

    oid = models.PositiveIntegerField(default=999)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ('-oid', 'created_on')

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class Forum(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110)
    description = models.TextField(default='')
    oid = models.PositiveIntegerField(default=999)
    category = models.ForeignKey(Category)
    admins = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(blank=True, null=True)
    num_topics = models.IntegerField(default=0)
    num_posts = models.IntegerField(default=0)

    users_like = models.CharField(max_length=2000,default="[]")
    users_taken = models.CharField(max_length=2000,default="[]")

    stars = models.FloatField(default=0.0)
    stared_people = models.IntegerField(default=0)

    last_post = models.ForeignKey(
        'Post', models.SET_NULL,
        verbose_name=_('Last post'),
        blank=True, null=True)

    class Meta:
        verbose_name = _("Forum")
        verbose_name_plural = _("Forums")
        ordering = ('oid', '-created_on')
        permissions = (
            ("sft_mgr_forum", _("Forum-Administrator")),
        )

    def do_star(self, rank):
        self.stars = (self.stars*self.stared_people + rank)/(self.stared_people + 1)
        self.stared_people += 1
        self.save()

    def change(self, user_id, old, new):
        users_like = self.get_users_like()
        users_taken = self.get_users_taken()
        if old == "like":
            users_like.remove(user_id)
        if old == "taken":
            users_taken.remove(user_id)
        if new == "like":
            users_like.append(user_id)
        if new == "taken":
            users_taken.append(user_id)
        self.users_taken = json.dumps(users_taken)
        self.users_like = json.dumps(users_like)
        self.save()

    def get_users_like(self):
        return json.loads(self.users_like)

    def get_users_taken(self):
        return json.loads(self.users_taken)

    def __str__(self):
        return self.name

    def _count_nums_topic(self):
        return self.topic_set.all().count()

    def _count_nums_post(self):
        return Post.objects.filter(topic__forum=self).count()

    @models.permalink
    def get_absolute_url(self):
        return ('lbforum_forum', (), {'forum_slug': self.slug})

    def update_state_info(self, last_post=None, commit=True):
        self.num_topics = self._count_nums_topic()
        self.num_posts = self._count_nums_post()
        if not last_post:
            last_post = Post.objects.filter(
                topic__forum=self).order_by('-created_on').first()
        self.last_post = last_post
        if commit:
            self.save()

    def is_admin(self, user):
        if user.has_perm('lbforum.sft_mgr_forum'):
            return True
        return self.admins.filter(pk=user.pk).exists()


@python_2_unicode_compatible
class TopicType(models.Model):
    forum = models.ForeignKey(Forum, verbose_name=_('Forum'))
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

LEVEL_CHOICES = (
    (30, _('Default')),
    (60, _('Distillate')),
)


@python_2_unicode_compatible
class Topic(models.Model):
    forum = models.ForeignKey(Forum, verbose_name=_('Forum'))
    topic_type = models.ForeignKey(
        TopicType, verbose_name=_('Topic Type'),
        blank=True, null=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL)

    post = models.ForeignKey(
        'Post', verbose_name=_('Post'),
        related_name='topics', blank=True, null=True)
    subject = models.CharField(max_length=999)

    num_views = models.IntegerField(default=0)
    num_replies = models.PositiveSmallIntegerField(default=0)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(blank=True, null=True)
    last_reply_on = models.DateTimeField(auto_now_add=True)
    last_post = models.ForeignKey(
        'Post', models.SET_NULL,
        verbose_name=_('Last post'),
        related_name='last_post_topics', blank=True, null=True)

    has_imgs = models.BooleanField(default=False)
    has_attachments = models.BooleanField(default=False)
    need_replay = models.BooleanField(default=False)  # need_reply :-)
    need_reply_attachments = models.BooleanField(default=False)

    closed = models.BooleanField(default=False)
    sticky = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)
    level = models.SmallIntegerField(choices=LEVEL_CHOICES, default=30)

    owns1 = models.IntegerField(default=-1)
    owns2 = models.IntegerField(default=-1)

    class Meta:
        ordering = ('-last_reply_on',)  # '-sticky'
        get_latest_by = ('created_on')
        verbose_name = _("Topic")
        verbose_name_plural = _("Topics")

    def __str__(self):
        return self.subject

    def _count_nums_replies(self):
        return self.posts.filter(topic_post=False).count()

    @models.permalink
    def get_absolute_url(self):
        return ('lbforum_topic', (), {'topic_id': self.id})

    def has_replied(self, user):
        if user.is_anonymous():
            return False
        return Post.objects.filter(posted_by=user, topic=self).count()

    def update_state_info(self, last_post=None, commit=True):
        self.num_replies = self._count_nums_replies()
        if not last_post:
            last_post = self.posts.order_by('-created_on').first()
        self.last_post = last_post
        if commit:
            self.save()


@python_2_unicode_compatible
class Post(models.Model):
    FORMAT_CHOICES = (
        ('bbcode', _('BBCode')),
        ('markdown', _('Markdown')),
        ('html', _('Html')),
    )
    topic = models.ForeignKey(Topic, verbose_name=_('Topic'), related_name='posts')
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL)
    poster_ip = models.GenericIPAddressField()
    topic_post = models.BooleanField(default=False)

    format = models.CharField(max_length=20, default='bbcode', choices=FORMAT_CHOICES)
    message = models.TextField()
    attachments = models.ManyToManyField(LBAttachment, blank=True)

    has_imgs = models.BooleanField(default=False)
    has_attachments = models.BooleanField(default=False)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(blank=True, null=True)
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='last_updated_by_posts',
        blank=True, null=True)

    class Meta:
        verbose_name = _("Post")
        verbose_name_plural = _("Posts")
        ordering = ('-created_on',)
        get_latest_by = ('created_on', )

    def __str__(self):
        return self.message[:80]

    def subject(self):
        if self.topic_post:
            return _('Topic: %s') % self.topic.subject
        return _('Re: %s') % self.topic.subject

    def file_attachments(self):
        return self.attachments.filter(is_img=False)

    def img_attachments(self):
        return self.attachments.filter(is_img=True)

    def _update_attachments_flag(self):
        self.has_attachments = self.attachments.filter(is_img=False).exists()
        self.has_imgs = self.attachments.filter(is_img=True).exists()
        self.save()
        if self.topic_post:
            topic = self.topic
            topic.has_attachments = self.has_attachments
            topic.has_imgs = self.has_imgs
            topic.save()

    def update_attachments(self, attachment_ids):
        self.attachments = LBAttachment.objects.filter(pk__in=attachment_ids)
        self._update_attachments_flag()

    @models.permalink
    def get_absolute_url(self):
        return ('lbforum_post', (), {'post_id': self.pk})

    def get_absolute_url_ext(self):
        topic = self.topic
        post_idx = topic.posts.filter(created_on__lte=self.created_on).count()
        page = (post_idx - 1) / elp_setttings.PER_PAGE + 1
        return '%s?page=%s#p%s' % (topic.get_absolute_url().replace("topic","chat"), page, self.pk)


@python_2_unicode_compatible
class LBForumUserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name='lbforum_profile',
        verbose_name=_('User'))

    nickname = models.CharField(
        _("Nickname"), max_length=255, blank=False, default='')
    avatar = ThumbnailerImageField(_("Avatar"), upload_to='imgs/avatars', blank=True, null=True)
    my_like_classes = models.CharField(max_length=2000, default="[]")
    my_taken_classes = models.CharField(max_length=2000, default="[]")
    friends = models.CharField(max_length=2000, default='[]')

    chatList = models.CharField(max_length=2000, default='{}')

    bio = models.TextField(blank=True)

    def __str__(self):
        return self.nickname or self.user.username

    def change_class(self, class_id, new_att):
        like_classes = self.get_like_classes()
        taken_classes = self.get_taken_classes()
        old = "not interested"
        if class_id in like_classes:
            like_classes.remove(class_id)
            old = "like"
        if class_id in taken_classes:
            taken_classes.remove(class_id)
            old = "taken"
        if new_att == "taken":
            taken_classes.append(class_id)
        if new_att == "like":
            like_classes.append(class_id)
        self.set_class(like_classes, 1)
        self.set_class(taken_classes, 2)
        return old


    def add_friend(self, user_id):
        friends = self.get_friend()
        if user_id not in friends:
            friends.append(user_id)
        self.set_friend(friends)

    def get_like_classes(self):
        return json.loads(self.my_like_classes)

    def get_taken_classes(self):
        return json.loads(self.my_taken_classes)

    def get_class(self):
        classes = self.get_like_classes() + self.get_taken_classes()
        classes = list(set(classes))
        return classes

    def set_class(self, x, op):
        if op == 1:
            self.my_like_classes = json.dumps(x)
        else:
            self.my_taken_classes = json.dumps(x)
        self.save()

    def get_chat_list(self):
        return json.loads(self.chatList)

    def add_chat(self, other, topic_id):
        chat_list = self.get_chat_list()
        if topic_id not in chat_list.keys():
            chat_list[other] = topic_id
        self.chatList = json.dumps(chat_list)
        self.save()

    def get_friend(self):
        return json.loads(self.friends)

    def set_friend(self, x):
        self.friends = json.dumps(x)
        self.save()

    def get_total_topics(self):
        return self.user.topic_set.count()

    def get_total_posts(self):
        return self.user.post_set.count()

    def get_absolute_url(self):
        return self.user.get_absolute_url()

    def get_avatar_url(self, size=48):
        if not self.avatar:
            return '%s%s' % (settings.STATIC_URL, 'lbforum/imgs/avatar.png', )
        options = {'size': (size, size), 'crop': True}
        return get_thumbnailer(self.avatar).get_thumbnail(options).url

    def get_large_avatar_url(self):
        return self.get_avatar_url(80)


def create_user_profile(sender, instance, created, **kwargs):
    if created:
        LBForumUserProfile.objects.create(user=instance)


def update_last_post(sender, instance, created, **kwargs):
    post = instance
    if created:
        topic = instance.topic
        forum = topic.forum
        topic.update_state_info(last_post=post)
        forum.update_state_info(last_post=post)


# post_save.connect(create_user_profile, sender=User)
post_save.connect(update_last_post, sender=Post)
