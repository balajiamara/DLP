import os
import json
import logging
import httpx
from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from classrooms.models import Classroom, ClassroomMembership

logger = logging.getLogger(__name__)

FASTAPI_INTERNAL_URL = os.getenv("FASTAPI_INTERNAL_URL", "http://127.0.0.1:8001")
INTERNAL_SERVICE_SECRET = os.getenv("INTERNAL_SERVICE_SECRET", "")


def is_user_in_classroom(user, classroom_id: int) -> bool:
    """Checks whether the user is an active member or assigned teacher of the classroom."""
    return (
        ClassroomMembership.objects.filter(
            classroom_id=classroom_id,
            user=user,
            status=ClassroomMembership.MembershipStatus.ACTIVE,
        ).exists()
        or Classroom.objects.filter(id=classroom_id, teacher=user).exists()
    )


class CourseChatStreamProxyView(APIView):
    """
    Proxies Course-Grounded RAG chat streaming requests to FastAPI.
    Enforces user authentication and classroom membership in Django before streaming.
    Relays Server-Sent Events (SSE) back to the client as tokens arrive.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        classroom_id = request.data.get("classroom_id")
        query = request.data.get("query")
        topic_id = request.data.get("topic_id")
        socratic_mode = bool(request.data.get("socratic_mode", False))

        if not classroom_id or not query:
            return Response(
                {"detail": "classroom_id and query are required fields."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            classroom_id = int(classroom_id)
        except (ValueError, TypeError):
            return Response(
                {"detail": "classroom_id must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Pre-authorization: Verify user belongs to classroom before proxying
        if not is_user_in_classroom(request.user, classroom_id):
            return Response(
                {"detail": "Access denied or classroom not found."},
                status=status.HTTP_403_FORBIDDEN,
            )

        target_url = f"{FASTAPI_INTERNAL_URL.rstrip('/')}/chat/course/stream"
        payload = {
            "student_user_id": request.user.id,
            "classroom_id": classroom_id,
            "topic_id": int(topic_id) if topic_id is not None else None,
            "query": str(query).strip(),
            "socratic_mode": socratic_mode,
        }
        headers = {
            "X-Internal-Secret": INTERNAL_SERVICE_SECRET,
            "Content-Type": "application/json",
        }

        async def stream_from_fastapi():
            client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=5.0))
            try:
                async with client.stream("POST", target_url, json=payload, headers=headers) as upstream_resp:
                    if upstream_resp.status_code != 200:
                        body = await upstream_resp.aread()
                        err_text = body.decode("utf-8", errors="replace")
                        yield f"data: {json.dumps({'type': 'error', 'detail': err_text})}\n\n"
                        return

                    async for line in upstream_resp.aiter_lines():
                        if line:
                            yield f"{line}\n\n"
            except Exception as exc:
                logger.error(f"Error proxying course chat stream from FastAPI: {exc}")
                yield f"data: {json.dumps({'type': 'error', 'detail': f'Proxy stream error: {exc}'})}\n\n"
            finally:
                await client.aclose()

        response = StreamingHttpResponse(stream_from_fastapi(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class GeneralChatStreamProxyView(APIView):
    """
    Proxies General Learning Mode chat streaming requests to FastAPI.
    Enforces user authentication and classroom membership in Django before streaming.
    Relays Server-Sent Events (SSE) back to the client as tokens arrive.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        classroom_id = request.data.get("classroom_id")
        query = request.data.get("query")
        socratic_mode = bool(request.data.get("socratic_mode", False))

        if not classroom_id or not query:
            return Response(
                {"detail": "classroom_id and query are required fields."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            classroom_id = int(classroom_id)
        except (ValueError, TypeError):
            return Response(
                {"detail": "classroom_id must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Pre-authorization: Verify user belongs to classroom before proxying
        if not is_user_in_classroom(request.user, classroom_id):
            return Response(
                {"detail": "Access denied or classroom not found."},
                status=status.HTTP_403_FORBIDDEN,
            )

        target_url = f"{FASTAPI_INTERNAL_URL.rstrip('/')}/chat/general/stream"
        payload = {
            "student_user_id": request.user.id,
            "classroom_id": classroom_id,
            "query": str(query).strip(),
            "socratic_mode": socratic_mode,
        }
        headers = {
            "X-Internal-Secret": INTERNAL_SERVICE_SECRET,
            "Content-Type": "application/json",
        }

        async def stream_from_fastapi():
            client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=5.0))
            try:
                async with client.stream("POST", target_url, json=payload, headers=headers) as upstream_resp:
                    if upstream_resp.status_code != 200:
                        body = await upstream_resp.aread()
                        err_text = body.decode("utf-8", errors="replace")
                        yield f"data: {json.dumps({'type': 'error', 'detail': err_text})}\n\n"
                        return

                    async for line in upstream_resp.aiter_lines():
                        if line:
                            yield f"{line}\n\n"
            except Exception as exc:
                logger.error(f"Error proxying general chat stream from FastAPI: {exc}")
                yield f"data: {json.dumps({'type': 'error', 'detail': f'Proxy stream error: {exc}'})}\n\n"
            finally:
                await client.aclose()

        response = StreamingHttpResponse(stream_from_fastapi(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class ChatFeedbackProxyView(APIView):
    """
    Proxies chat interaction feedback (thumbs up / thumbs down) to FastAPI's evaluation service.
    Requires user authentication, attaches internal service secret, and relays response.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        log_id = request.data.get("log_id") or request.data.get("interaction_id")
        rating = request.data.get("rating")
        reason = request.data.get("reason")

        if not log_id or not rating:
            return Response(
                {"detail": "log_id and rating are required fields."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if rating not in ("up", "down"):
            return Response(
                {"detail": "rating must be either 'up' or 'down'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_url = f"{FASTAPI_INTERNAL_URL.rstrip('/')}/evaluation/feedback"
        payload = {
            "log_id": str(log_id),
            "rating": rating,
            "reason": reason,
        }
        headers = {
            "X-Internal-Secret": INTERNAL_SERVICE_SECRET,
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=5.0) as client:
                upstream_resp = client.post(target_url, json=payload, headers=headers)
                data = (
                    upstream_resp.json()
                    if upstream_resp.headers.get("content-type", "").startswith("application/json")
                    else upstream_resp.text
                )
                return Response(data, status=upstream_resp.status_code)
        except Exception as exc:
            logger.error(f"Error proxying feedback to FastAPI: {exc}")
            return Response(
                {"detail": f"Failed to record feedback: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

