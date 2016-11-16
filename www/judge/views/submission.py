# -*- coding: utf-8 -*-
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.core.urlresolvers import reverse
from djangoutils import setup_paginator, get_or_none
from django.contrib.auth.models import User
from django.http import Http404, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from guardian.core import ObjectPermissionChecker
from ..models import Problem, Submission
from ..forms import SubmissionFilterForm

def rejudge(request, id):
    submission = get_object_or_404(Submission, id=id)
    if submission.user != request.user and not request.user.is_superuser:
        return HttpResponseForbidden()
    submission.rejudge()
    return redirect(reverse("judge-submission-details", kwargs={"id": id}))

def recent(request, page=1):
    checker = ObjectPermissionChecker(request.user)
    submissions = Submission.objects.all().order_by("-id")

    filters = {}

    empty_message = u"제출된 답안이 없습니다."
    title_add = []

    # only superuser can see all nonpublic submissions.
    # as an exception, if we are filtering by a problem, the author can see
    # nonpublic submissions. also, everybody can see their nonpublic
    # submissions.
    only_public = not request.user.is_superuser

    if request.GET.get("problem"):
        slug = request.GET["problem"]
        problem = get_object_or_404(Problem, slug=slug)

        if request.user == problem.user or checker.has_perm('read_problem', problem):
            only_public = False

        if (problem.state != Problem.PUBLISHED and
             request.user != problem.user and
             not checker.has_perm('read_problem', problem)):
            raise Http404
        submissions = submissions.filter(problem=problem)

        title_add.append(slug)
        filters["problem"] = slug

    if "state" in request.GET:
        state = request.GET["state"]
        if not state in [None, '']:
            submissions = submissions.filter(state=state)
            filters["state"] = state
            title_add.append(Submission.STATES_KOR[int(state)])

    if request.GET.get("order_by"):
        order_by = request.GET.get("order_by")
        if order_by.endswith('id') or order_by.endswith('length') or order_by.endswith('time'):
            submissions = submissions.order_by(order_by)

    if request.GET.get("user"):
        username = request.GET["user"]
        user = get_or_none(User, username=username)
        if not user:
            empty_message = u"해당 사용자가 없습니다."
            submissions = submissions.none()
        else:
            submissions = submissions.filter(user=user)
        filters["user"] = username
        title_add.append(username)
        if user == request.user:
            only_public = False

    if only_public:
        submissions = submissions.filter(is_public=True)

    if request.GET.get("language"):
        language = request.GET["language"]
        submissions = submissions.filter(language=language)
        filters["language"] = language
        title_add.append(language)

    filters_form = SubmissionFilterForm(initial=filters)

    return render(request, "submission/recent.html",
                  {"title": u"답안 목록" + (": " if title_add else "") + ",".join(title_add),
                   "filter_form" : filters_form,
                   "empty_message": empty_message,
                   "pagination": setup_paginator(submissions, page,
                                                 "judge-submission-recent", {}, filters)})

@login_required
def details(request, id):
    from django.conf import settings

    checker = ObjectPermissionChecker(request.user)
    submission = get_object_or_404(Submission, id=id)
    problem = submission.problem
    if (not problem.was_solved_by(request.user) and
            submission.user != request.user and
            problem.user != request.user and
            not checker.has_perm('read_problem', problem)):
        return HttpResponseForbidden()
    message = ''
    if submission.state == Submission.ACCEPTED:
        now = datetime.now()
        for item in settings.SOLVED_CAMPAIGN:
            if (item['problem'] == problem.slug and
                item['begin'] <= now <= item['end']):
                message = item['message']
                break
    return render(request, "submission/details.html",
                  {"title": u"답안 보기",
                   "submission": submission,
                   "message": message,
                   "problem": problem})
