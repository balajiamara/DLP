"""
Explainable, Rule-Based At-Risk Signal Module for Classrooms.

Note on Scalability:
This evaluation is recomputed dynamically on request since classroom-scale data (10-100 students)
makes on-demand calculation fast and lightweight. If scaling to institution-wide scale (10,000+ students),
this calculation could easily be offloaded to a scheduled Celery cron task or cached in Redis.
"""

from django.utils import timezone
from django.db import models

from syllabus.models import Topic, TopicProgress
from doubts.models import Doubt, DoubtReply
from assessments.models import Submission, QuizAttempt
from .models import ClassroomMembership


INACTIVITY_DAYS_THRESHOLD = 4
BEHIND_PACE_PERCENT_THRESHOLD = 20.0
LOW_QUIZ_AVG_THRESHOLD = 50.0


def get_student_at_risk_status(student, classroom, classroom_avg_percent=None):
    """
    Evaluates whether a student in a classroom is at-risk based on an explainable, rule-based heuristic.

    At-risk rule:
      at_risk is True ONLY IF no_activity_days >= INACTIVITY_DAYS_THRESHOLD (4 days)
      AND at least one secondary signal is True:
        1. behind_expected_pace (> 20.0% below classroom average progress)
        2. low_recent_quiz_average (quiz average < 50.0%, requiring >= 1 attempt)

    Returns:
      {
          "at_risk": bool,
          "no_activity_days": int,
          "reasons": list[str]
      }
    """
    now = timezone.now()

    # 1. Gather all activity timestamps for this student in this classroom
    timestamps = []

    # a) TopicProgress updates
    tp_latest = TopicProgress.objects.filter(
        student=student,
        topic__module__course__classroom=classroom
    ).aggregate(max_updated=models.Max('updated_at'))['max_updated']
    if tp_latest:
        timestamps.append(tp_latest)

    # b) Quiz attempts
    qa_latest = QuizAttempt.objects.filter(
        student=student,
        quiz__classroom=classroom
    ).aggregate(max_attempted=models.Max('attempted_at'))['max_attempted']
    if qa_latest:
        timestamps.append(qa_latest)

    # c) Submissions
    sub_latest = Submission.objects.filter(
        student=student,
        assignment__classroom=classroom
    ).aggregate(max_submitted=models.Max('submitted_at'))['max_submitted']
    if sub_latest:
        timestamps.append(sub_latest)

    # d) Doubts posted
    doubt_latest = Doubt.objects.filter(
        author=student,
        classroom=classroom
    ).aggregate(max_created=models.Max('created_at'))['max_created']
    if doubt_latest:
        timestamps.append(doubt_latest)

    # e) Doubt replies posted
    reply_latest = DoubtReply.objects.filter(
        author=student,
        doubt__classroom=classroom
    ).aggregate(max_created=models.Max('created_at'))['max_created']
    if reply_latest:
        timestamps.append(reply_latest)

    # Determine latest activity date
    if timestamps:
        most_recent_activity = max(timestamps)
        no_activity_days = (now - most_recent_activity).days
    else:
        # If no activity recorded, fallback to membership join date
        membership = ClassroomMembership.objects.filter(
            user=student,
            classroom=classroom,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        ).first()
        if membership:
            no_activity_days = (now - membership.joined_at).days
        else:
            no_activity_days = 999

    # 2. Calculate student's progress % and check behind_expected_pace
    topics = Topic.objects.filter(module__course__classroom=classroom)
    total_topics_count = topics.count()

    completed_count = TopicProgress.objects.filter(
        student=student,
        topic__in=topics,
        learning_state__in=['COMPLETED', 'MASTERED']
    ).count()

    student_percent = round((completed_count / total_topics_count * 100), 1) if total_topics_count > 0 else 0.0

    # Calculate classroom average if not provided
    if classroom_avg_percent is None:
        active_student_memberships = ClassroomMembership.objects.filter(
            classroom=classroom,
            status=ClassroomMembership.MembershipStatus.ACTIVE,
            role_in_classroom='STUDENT'
        ).select_related('user')
        active_students = [m.user for m in active_student_memberships]
        active_student_count = len(active_students)

        if total_topics_count == 0 or active_student_count == 0:
            classroom_avg_percent = 0.0
        else:
            student_percents = []
            for st in active_students:
                c_cnt = TopicProgress.objects.filter(
                    student=st,
                    topic__in=topics,
                    learning_state__in=['COMPLETED', 'MASTERED']
                ).count()
                student_percents.append(round((c_cnt / total_topics_count * 100), 1))
            classroom_avg_percent = round(sum(student_percents) / len(student_percents), 1) if student_percents else 0.0

    pace_diff = round(classroom_avg_percent - student_percent, 1)
    behind_expected_pace = pace_diff > BEHIND_PACE_PERCENT_THRESHOLD

    # 3. Calculate low_recent_quiz_average
    quiz_attempts = QuizAttempt.objects.filter(quiz__classroom=classroom, student=student)
    attempts_count = quiz_attempts.count()

    if attempts_count == 0:
        low_recent_quiz_average = False
        quiz_avg = None
    else:
        avg_score = quiz_attempts.aggregate(avg_score=models.Avg('score'))['avg_score'] or 0.0
        quiz_avg = round(avg_score, 1)
        low_recent_quiz_average = quiz_avg < LOW_QUIZ_AVG_THRESHOLD

    # 4. Formulate At-Risk Evaluation & Explainable Reasons
    reasons = []

    if no_activity_days >= INACTIVITY_DAYS_THRESHOLD:
        reasons.append(f"No activity in {no_activity_days} days")

    if behind_expected_pace:
        reasons.append(f"{pace_diff}% behind classroom average progress")

    if low_recent_quiz_average:
        reasons.append(f"Low quiz average score ({quiz_avg}%)")

    at_risk = (no_activity_days >= INACTIVITY_DAYS_THRESHOLD) and (behind_expected_pace or low_recent_quiz_average)

    return {
        "at_risk": at_risk,
        "no_activity_days": no_activity_days,
        "reasons": reasons
    }
