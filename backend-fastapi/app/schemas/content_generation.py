"""
Pydantic Schemas for AI Content Generation (Step 40)

Defines strict models for:
1. LLM structured generation output (QuizDraftSchema, StudyPlanDraftSchema)
2. API requests and responses for the review-before-save gate.
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


class QuizQuestionDraft(BaseModel):
    question: str = Field(..., description="The question prompt text.")
    option_a: str = Field(..., description="Option A choice text.")
    option_b: str = Field(..., description="Option B choice text.")
    option_c: str = Field(..., description="Option C choice text.")
    option_d: str = Field(..., description="Option D choice text.")
    correct_option: Literal["A", "B", "C", "D"] = Field(
        ...,
        description="The letter of the correct option (A, B, C, or D). Note: validated for format only; factual correctness requires teacher review."
    )
    explanation: str = Field(
        ...,
        description="Detailed pedagogical explanation for why the chosen option is correct."
    )


class QuizDraftSchema(BaseModel):
    title: str = Field(..., description="Title of the quiz.")
    questions: List[QuizQuestionDraft] = Field(
        ...,
        description="List of multiple-choice questions grounded in provided course material."
    )


class StudyPlanTaskDraft(BaseModel):
    title: str = Field(..., description="Title of the study task or milestone.")
    description: str = Field(..., description="Actionable instructions for what and how the student should study.")
    target_topic_name: Optional[str] = Field(None, description="Name of the topic or concept this task targets.")
    suggested_pacing: str = Field(..., description="Suggested duration or pacing (e.g. 'Day 1-2' or '45 mins').")
    suggested_due_date: Optional[str] = Field(None, description="Optional target completion date (YYYY-MM-DD).")


class StudyPlanDraftSchema(BaseModel):
    title: str = Field(..., description="Title of the study plan.")
    overview: str = Field(..., description="High-level pedagogical summary explaining the plan's focus.")
    tasks: List[StudyPlanTaskDraft] = Field(
        ...,
        description="Ordered list of study tasks tailored to student's current progress and weak areas."
    )


# --- API Request & Response Schemas ---

class GenerateQuizRequest(BaseModel):
    classroom_id: int = Field(..., description="ID of the classroom.")
    topic_id: int = Field(..., description="ID of the syllabus topic to ground the quiz in.")
    teacher_user_id: int = Field(..., description="User ID of the teacher requesting generation.")
    num_questions: int = Field(5, ge=1, le=20, description="Number of questions to generate (1-20).")


class GenerateStudyPlanRequest(BaseModel):
    classroom_id: int = Field(..., description="ID of the classroom.")
    student_user_id: int = Field(..., description="User ID of the student the plan is tailored for.")
    requesting_user_id: int = Field(..., description="User ID of the user requesting the plan (must be student self or classroom teacher).")
    goal_description: str = Field(..., min_length=3, description="Description of the student's study goal.")
    deadline: Optional[str] = Field(None, description="Optional target deadline string.")


class GeneratedDraftResponse(BaseModel):
    id: int = Field(..., description="ID of the created holding draft record.")
    classroom: int = Field(..., description="Classroom ID.")
    content_type: str = Field(..., description="QUIZ or STUDY_PLAN.")
    status: str = Field(..., description="Status of the draft (default DRAFT).")
    content: Dict[str, Any] = Field(..., description="Validated structured content.")
    topic: Optional[int] = Field(None, description="Topic ID if grounded in a topic.")
    created_by: int = Field(..., description="User ID of the creator.")
    target_student: Optional[int] = Field(None, description="Target student ID for study plans.")
    requires_teacher_fact_check: bool = Field(
        True,
        description="Explicit notice: format has been validated by schema, but factual correctness requires human teacher review."
    )
    review_notice: str = Field(
        "Schema validation confirms structure and format only. Factual accuracy, pedagogical relevance, and correct answer selection must be verified by a teacher before approval.",
        description="Human review gate disclaimer."
    )
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
