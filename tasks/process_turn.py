"""
Celery task: process one ConversationTurn of a multi-turn call session.

Flow
----
1. Load turn + session
2. Audit input audio
3. Transcribe caller audio (STT)
4. Build history
5. Detect closing early
6. Route conversation through intent/rules/LLM layer
7. Save AI text result
8. Generate TTS reply
9. Audit output audio
10. Update session + follow-up + transfer + closing

Notes
-----
- Safe with models that do NOT contain optional timestamp fields
  like stt_started_at / llm_started_at / tts_started_at.
- Follow-up creation is defensive and tries common field names.
- Keeps the pipeline alive instead of crashing on optional fields.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from celery import shared_task
from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.voice_calls.models import CallSession, ConversationTurn
from services.conversation_router import route_turn
from services.intent_engine import detect_intent, normalize_language

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generic safe model helpers
# ---------------------------------------------------------------------------

def _instance_has_field(instance, field_name: str) -> bool:
    return any(f.name == field_name for f in instance._meta.fields)


def _model_has_field(model_cls, field_name: str) -> bool:
    return any(f.name == field_name for f in model_cls._meta.fields)


def _safe_update_field(instance, field_name: str, value) -> None:
    """
    Update a field only if it exists on the model.
    """
    if _instance_has_field(instance, field_name):
        setattr(instance, field_name, value)
        instance.save(update_fields=[field_name])


def _safe_update_many(instance, values: Dict[str, Any]) -> None:
    """
    Update multiple fields safely, ignoring missing fields.
    """
    update_fields: List[str] = []
    for field_name, value in values.items():
        if _instance_has_field(instance, field_name):
            setattr(instance, field_name, value)
            update_fields.append(field_name)

    if update_fields:
        instance.save(update_fields=update_fields)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _build_history(session: CallSession) -> List[dict]:
    """
    Build compact history from previous READY turns only.
    """
    turns = (
        session.turns
        .filter(status=ConversationTurn.Status.READY)
        .order_by("turn_number")
    )

    history: List[dict] = []
    for t in turns:
        if getattr(t, "transcript_text", None):
            history.append({"role": "user", "content": t.transcript_text})
        if getattr(t, "ai_response_text", None):
            history.append({"role": "assistant", "content": t.ai_response_text})

    return history[-12:]


def _fail(turn: ConversationTurn, reason: str) -> None:
    _safe_update_many(turn, {
        "status": ConversationTurn.Status.FAILED,
        "error_message": reason,
    })
    logger.error(f"[process_turn] FAILED | turn={turn.id} reason={reason}")


def _increment_session_turns(session: CallSession) -> None:
    CallSession.objects.filter(pk=session.pk).update(
        total_turns=F("total_turns") + 1,
    )


def _trigger_session_transfer(session: CallSession, reason: str) -> None:
    ended = timezone.now()
    duration = None
    if getattr(session, "started_at", None):
        duration = int((ended - session.started_at).total_seconds())

    update_values = {
        "transfer_triggered": True,
        "transfer_reason": reason,
        "status": CallSession.Status.TRANSFERRED,
        "ended_at": ended,
    }
    if duration is not None and _instance_has_field(session, "duration_seconds"):
        update_values["duration_seconds"] = duration

    CallSession.objects.filter(pk=session.pk).update(**update_values)


def _finalize_session(session: CallSession, status: str) -> None:
    ended = timezone.now()
    duration = 0
    if getattr(session, "started_at", None):
        duration = int((ended - session.started_at).total_seconds())

    update_values = {
        "status": status,
        "ended_at": ended,
    }
    if _instance_has_field(session, "duration_seconds"):
        update_values["duration_seconds"] = duration

    CallSession.objects.filter(pk=session.pk).update(**update_values)


def _set_session_processing(session: CallSession) -> None:
    """
    If PROCESSING exists, use it; otherwise fallback to ACTIVE.
    """
    try:
        processing_status = getattr(CallSession.Status, "PROCESSING")
    except Exception:
        processing_status = getattr(CallSession.Status, "ACTIVE", session.status)

    CallSession.objects.filter(pk=session.pk).update(status=processing_status)


def _set_session_active_if_possible(session: CallSession) -> None:
    try:
        active_status = getattr(CallSession.Status, "ACTIVE")
        CallSession.objects.filter(pk=session.pk).update(status=active_status)
    except Exception:
        pass


def _transcribe_audio(audio_path: str) -> str:
    """
    Try common transcription entry points without forcing one exact function name.
    """
    from services import openai_transcription_service as stt_service

    candidate_names = [
        "transcribe",
        "transcribe_audio",
        "transcribe_file",
        "transcribe_wav",
    ]

    for name in candidate_names:
        fn = getattr(stt_service, name, None)
        if callable(fn):
            return fn(audio_path)

    raise RuntimeError(
        "No transcription function found in services.openai_transcription_service. "
        "Expected one of: transcribe, transcribe_audio, transcribe_file, transcribe_wav"
    )


# ---------------------------------------------------------------------------
# Follow-up / alert helpers
# ---------------------------------------------------------------------------

def _create_follow_up_if_needed(
    session: CallSession,
    caller_text: str,
    result: Dict[str, Any],
) -> None:
    """
    Create a follow-up record for commercial leads or unanswered inquiries.

    Tries multiple common field names to fit your existing model.
    """
    if not result.get("follow_up"):
        return

    try:
        from apps.portal.models import FollowUp

        note = (result.get("follow_up_note") or caller_text or "").strip()
        follow_up_type = (result.get("follow_up_type") or "inquiry").strip()

        # duplicate guard if reverse relation exists
        if hasattr(session, "followups"):
            try:
                if session.followups.filter(notes__icontains=note[:40]).exists():
                    logger.info(f"[process_turn] follow-up skipped (duplicate-ish) | session={session.id}")
                    return
            except Exception:
                pass

        kwargs: Dict[str, Any] = {"session": session}

        if hasattr(FollowUp, "Status"):
            kwargs["status"] = getattr(FollowUp.Status, "PENDING", "pending")
        elif _model_has_field(FollowUp, "status"):
            kwargs["status"] = "pending"

        if hasattr(FollowUp, "Priority"):
            kwargs["priority"] = getattr(FollowUp.Priority, "MEDIUM", "medium")
        elif _model_has_field(FollowUp, "priority"):
            kwargs["priority"] = "medium"

        if _model_has_field(FollowUp, "notes"):
            kwargs["notes"] = f"[{follow_up_type}] {note}"
        elif _model_has_field(FollowUp, "note"):
            kwargs["note"] = f"[{follow_up_type}] {note}"
        elif _model_has_field(FollowUp, "description"):
            kwargs["description"] = f"[{follow_up_type}] {note}"

        if _model_has_field(FollowUp, "source"):
            kwargs["source"] = "intent_router"

        FollowUp.objects.create(**kwargs)
        if _instance_has_field(session, "needs_followup"):
            CallSession.objects.filter(pk=session.pk).update(needs_followup=True)

        logger.info(
            f"[process_turn] follow-up created | session={session.id} "
            f"type={follow_up_type}"
        )

        # Fire email alert so admin is notified immediately
        try:
            from apps.portal.models import Alert
            from apps.portal.tasks import send_alert_notification

            alert, created = Alert.objects.get_or_create(
                session=session,
                alert_type=Alert.AlertType.HUMAN_REQUESTED,
                defaults=dict(
                    severity=Alert.Severity.MEDIUM,
                    title=f"Follow-up required — {getattr(session, 'caller_number', 'unknown')}",
                    description=f"[{follow_up_type}] {note[:300]}",
                    send_email=True,
                ),
            )
            if created:
                send_alert_notification.delay(str(alert.id))
                logger.info(f"[process_turn] follow-up alert queued | session={session.id}")
        except Exception as email_exc:
            logger.warning(f"[process_turn] follow-up alert failed: {email_exc}", exc_info=True)

    except Exception as exc:
        logger.warning(f"[process_turn] follow-up creation failed: {exc}", exc_info=True)


def _handle_rag_failure(session: CallSession, question: str) -> None:
    """
    When RAG cannot answer:
    1. Mark session needs_followup = True if field exists
    2. Create FollowUp if possible
    3. Create Alert and queue email notification if possible
    """
    try:
        from apps.portal.models import Alert, FollowUp
        from apps.portal.tasks import send_alert_notification

        if _instance_has_field(session, "needs_followup"):
            CallSession.objects.filter(pk=session.pk).update(needs_followup=True)

        alert, created = Alert.objects.get_or_create(
            session=session,
            alert_type=Alert.AlertType.NO_ANSWER,
            defaults=dict(
                severity=Alert.Severity.MEDIUM,
                title=f"RAG failure — {getattr(session, 'caller_number', 'unknown')}",
                description=(
                    "AI could not find a reliable answer from the knowledge base.\n"
                    f"Caller question: {question[:200]}"
                ),
                send_email=True,
            ),
        )

        if hasattr(session, "followups"):
            try:
                exists = session.followups.filter(source="rag_failure").exists()
            except Exception:
                exists = False
        else:
            exists = False

        if not exists:
            kwargs: Dict[str, Any] = {
                "session": session,
                "alert": alert,
            }

            if hasattr(FollowUp, "Status"):
                kwargs["status"] = getattr(FollowUp.Status, "PENDING", "pending")
            elif _model_has_field(FollowUp, "status"):
                kwargs["status"] = "pending"

            if hasattr(FollowUp, "Priority"):
                kwargs["priority"] = getattr(FollowUp.Priority, "MEDIUM", "medium")
            elif _model_has_field(FollowUp, "priority"):
                kwargs["priority"] = "medium"

            if _model_has_field(FollowUp, "source"):
                kwargs["source"] = "rag_failure"

            rag_note = (
                "AI could not find a reliable answer from the knowledge base.\n"
                f"Caller question: {question[:200]}"
            )

            if _model_has_field(FollowUp, "notes"):
                kwargs["notes"] = rag_note
            elif _model_has_field(FollowUp, "note"):
                kwargs["note"] = rag_note

            FollowUp.objects.create(**kwargs)

        if created:
            send_alert_notification.delay(str(alert.id))

        logger.info(
            f"[process_turn] RAG failure handled | session={session.id} "
            f"alert_created={created}"
        )
    except Exception as exc:
        logger.error(f"[process_turn] RAG failure handler error: {exc}", exc_info=True)


# ---------------------------------------------------------------------------
# Main task
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=60,
    name="tasks.process_turn",
)
def process_turn(self, turn_id: str) -> dict:
    logger.info(f"[process_turn] start | turn={turn_id}")

    try:
        turn = ConversationTurn.objects.select_related("session").get(id=turn_id)
    except ConversationTurn.DoesNotExist:
        logger.error(f"[process_turn] turn not found: {turn_id}")
        return {"status": "error", "reason": "turn_not_found"}

    session = turn.session
    session_language = normalize_language(getattr(session, "language", "en"))

    # Mark turn/session as processing
    _safe_update_field(turn, "status", ConversationTurn.Status.PROCESSING)
    _set_session_processing(session)

    # 1) Audit input audio
    input_path = getattr(turn, "audio_input_path", "")
    input_exists = bool(input_path and os.path.isfile(input_path))
    input_size = os.path.getsize(input_path) if input_exists else None

    _safe_update_many(turn, {
        "audio_input_exists": input_exists,
        "audio_input_size": input_size,
    })

    logger.info(
        f"[process_turn] input_audio | turn={turn_id} "
        f"exists={input_exists} size={input_size} path={input_path}"
    )

    if not input_exists:
        _fail(turn, f"Input audio file not found: {input_path}")
        return {"status": "failed", "reason": "input_audio_missing", "turn_id": turn_id}

    # 2) STT
    _safe_update_field(turn, "stt_started_at", timezone.now())

    try:
        transcript = _transcribe_audio(input_path)
    except Exception as exc:
        logger.error(f"[process_turn] STT failed | turn={turn_id}: {exc}", exc_info=True)
        _fail(turn, f"STT failed: {exc}")
        raise

    transcript = (transcript or "").strip()

    _safe_update_many(turn, {
        "transcript_text": transcript,
        "stt_completed_at": timezone.now(),
    })

    logger.info(f"[process_turn] STT done | turn={turn_id} len={len(transcript)}")

    if not transcript:
        _fail(turn, "Empty transcript after transcription")
        return {"status": "failed", "reason": "empty_transcript", "turn_id": turn_id}

    # 3) Early closing detection
    intent_data = detect_intent(transcript, language=session_language)
    history = _build_history(session)

    if intent_data.get("closing"):
        from apps.portal.models import SiteConfig
        _company = SiteConfig.get_solo().company_name
        result: Dict[str, Any] = {
            "answer": (
                f"شكرًا لاتصالك بـ {_company}. مع السلامة."
                if session_language == "ar"
                else f"Thank you for calling {_company}. Goodbye."
            ),
            "transfer": False,
            "reason": "",
            "closing": True,
            "rag_no_answer": False,
            "follow_up": False,
            "follow_up_type": "",
            "follow_up_note": "",
        }
        logger.info(f"[process_turn] early closing detected | turn={turn_id}")
    else:
        # 4) Routing / LLM
        _safe_update_field(turn, "llm_started_at", timezone.now())

        try:
            result = route_turn(
                question=transcript,
                history=history,
                vector_store_id=getattr(settings, "OPENAI_VECTOR_STORE_ID", ""),
                language=session_language,
            )
        except Exception as exc:
            logger.error(f"[process_turn] routing/LLM failed | turn={turn_id}: {exc}", exc_info=True)
            _fail(turn, f"Routing/LLM failed: {exc}")
            raise

        _safe_update_field(turn, "llm_completed_at", timezone.now())

    answer_text = (result.get("answer") or "").strip()
    needs_transfer = bool(result.get("transfer", False))
    transfer_reason = result.get("reason", "") or ""
    closing = bool(result.get("closing", False))
    rag_no_answer = bool(result.get("rag_no_answer", False))
    follow_up = bool(result.get("follow_up", False))
    follow_up_type = result.get("follow_up_type", "") or ""
    follow_up_note = result.get("follow_up_note", "") or ""

    _safe_update_many(turn, {
        "ai_response_text": answer_text,
        "transfer_needed": needs_transfer,
        "transfer_reason": transfer_reason,
        "closing_detected": closing,
        "rag_failure": rag_no_answer,
    })

    logger.info(
        f"[process_turn] routed | turn={turn_id} "
        f"reply_len={len(answer_text)} transfer={needs_transfer} "
        f"closing={closing} rag_no_answer={rag_no_answer} "
        f"follow_up={follow_up} follow_up_type={follow_up_type}"
    )

    if not answer_text:
        _fail(turn, "Empty AI answer")
        return {"status": "failed", "reason": "empty_ai_answer", "turn_id": turn_id}

    # 5) TTS
    from services.openai_tts_service import synthesise

    _safe_update_field(turn, "tts_started_at", timezone.now())

    try:
        audio_path = synthesise(text=answer_text, turn_id=str(turn_id))
    except Exception as exc:
        logger.error(f"[process_turn] TTS failed | turn={turn_id}: {exc}", exc_info=True)

        _safe_update_many(turn, {
            "error_message": f"TTS failed: {exc}",
            "tts_completed_at": timezone.now(),
            "status": ConversationTurn.Status.FAILED,
        })

        if needs_transfer:
            _trigger_session_transfer(session, transfer_reason)

        return {
            "status": "failed",
            "stage": "tts",
            "turn_id": turn_id,
            "transfer": needs_transfer,
        }

    # 6) Audit output audio
    out_exists = os.path.isfile(audio_path)
    out_size = os.path.getsize(audio_path) if out_exists else None

    _safe_update_many(turn, {
        "audio_response_path": audio_path,
        "audio_response_exists": out_exists,
        "audio_response_size": out_size,
        "tts_completed_at": timezone.now(),
        "status": ConversationTurn.Status.READY,
    })

    logger.info(
        f"[process_turn] TTS done | turn={turn_id} "
        f"path={audio_path} exists={out_exists} size={out_size}"
    )

    # 7) Update counters
    _increment_session_turns(session)

    # 8) Follow-up / alert handling
    if follow_up:
        _create_follow_up_if_needed(
            session=session,
            caller_text=transcript,
            result={
                "follow_up": follow_up,
                "follow_up_type": follow_up_type,
                "follow_up_note": follow_up_note,
            },
        )

    if rag_no_answer:
        _handle_rag_failure(session, transcript)

    # 9) Transfer / closing / active
    if needs_transfer:
        _trigger_session_transfer(session, transfer_reason)
        logger.info(f"[process_turn] transfer triggered | session={session.id}")

    elif closing:
        _finalize_session(session, CallSession.Status.COMPLETED)
        logger.info(f"[process_turn] closing detected — session finalized | session={session.id}")

    else:
        _set_session_active_if_possible(session)

    return {
        "status": "ready",
        "turn_id": turn_id,
        "session_id": str(session.id),
        "audio_path": audio_path,
        "transfer": needs_transfer,
        "transfer_reason": transfer_reason,
        "closing": closing,
        "rag_no_answer": rag_no_answer,
        "follow_up": follow_up,
        "follow_up_type": follow_up_type,
        "follow_up_note": follow_up_note,
    }
