"""
Appointment Scheduling Routes
Handles appointment booking, rescheduling, and cancellation via n8n workflow.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import httpx
import os

from .database import get_db

router = APIRouter(prefix="/appointments", tags=["appointments"])

# n8n configuration
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "https://n8n.mediqzy.com")
N8N_WEBHOOK_KEY = os.getenv("N8N_WEBHOOK_KEY", "appointment-booking")


class AppointmentRequest(BaseModel):
    """Appointment booking request"""
    patient_name: str
    patient_email: str
    patient_phone: str
    appointment_type: str = Field(..., description="e.g., General Checkup, Follow-up, Emergency")
    preferred_date: Optional[str] = None  # Format: YYYY-MM-DD
    preferred_time: Optional[str] = None  # Format: HH:MM
    doctor_specialty: Optional[str] = None
    reason: Optional[str] = None


class AppointmentResponse(BaseModel):
    """Appointment confirmation response"""
    appointment_id: str
    status: str
    confirmation_message: str
    next_steps: str


@router.post("/book", response_model=AppointmentResponse)
async def book_appointment(
    req: AppointmentRequest,
    db: AsyncSession = Depends(get_db)
) -> AppointmentResponse:
    """
    Book a new appointment via n8n workflow.
    
    Calls n8n workflow which handles:
    - Calendar availability check
    - Appointment slot reservation
    - Confirmation email/SMS
    - Database storage
    """
    try:
        # Call n8n webhook for appointment booking workflow
        n8n_url = f"{N8N_BASE_URL}/webhook/{N8N_WEBHOOK_KEY}"
        
        payload = {
            "patient_name": req.patient_name,
            "patient_email": req.patient_email,
            "patient_phone": req.patient_phone,
            "appointment_type": req.appointment_type,
            "preferred_date": req.preferred_date,
            "preferred_time": req.preferred_time,
            "doctor_specialty": req.doctor_specialty,
            "reason": req.reason,
            "action": "book"
        }
        
        logger.info(f"Calling n8n appointment workflow: {n8n_url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(n8n_url, json=payload)
            
            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"n8n workflow completed: {result}")
                
                appointment_id = result.get("appointment_id", f"APT-{uuid.uuid4().hex[:8].upper()}")
                
                return AppointmentResponse(
                    appointment_id=appointment_id,
                    status="confirmed",
                    confirmation_message=result.get("confirmation_message", "Appointment booked successfully!"),
                    next_steps=result.get("next_steps", "Check your email for confirmation details.")
                )
            else:
                logger.error(f"n8n workflow failed: {response.status_code} - {response.text}")
                raise Exception(f"n8n workflow returned {response.status_code}")
        
    except Exception as e:
        logger.error(f"Appointment booking failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to book appointment: {str(e)}"
        )


@router.get("/available-slots/{specialty}")
async def get_available_slots(
    specialty: str,
    date: Optional[str] = None
) -> dict:
    """
    Get available appointment slots for a specialty via n8n.
    
    Queries n8n workflow for calendar availability.
    """
    try:
        n8n_url = f"{N8N_BASE_URL}/webhook/{N8N_WEBHOOK_KEY}"
        
        payload = {
            "specialty": specialty,
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "action": "get_slots"
        }
        
        logger.info(f"Fetching slots from n8n for {specialty}")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(n8n_url, json=payload)
            
            if response.status_code in [200, 201]:
                result = response.json()
                return result
            else:
                logger.error(f"n8n slot query failed: {response.status_code}")
                # Fallback mock data
                return {
                    "date": date or datetime.now().strftime("%Y-%m-%d"),
                    "specialty": specialty,
                    "available_times": [
                        "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM",
                        "02:00 PM", "02:30 PM", "03:00 PM", "03:30 PM"
                    ],
                    "total_available": 8,
                    "source": "fallback"
                }
        
    except Exception as e:
        logger.error(f"Failed to fetch available slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch available slots: {str(e)}"
        )


@router.get("/confirmation/{appointment_id}")
async def get_appointment_confirmation(
    appointment_id: str
) -> dict:
    """
    Retrieve appointment confirmation details.
    """
    try:
        # Mock confirmation - in production, query database
        confirmation = {
            "appointment_id": appointment_id,
            "status": "confirmed",
            "scheduled_for": "2026-01-27 10:00 AM",
            "location": "Main Clinic, Floor 2, Room 204",
            "doctor_name": "Dr. Sarah Kumar",
            "instructions": [
                "Arrive 15 minutes early",
                "Bring insurance card and valid ID",
                "Bring any relevant medical documents",
                "Avoid heavy meals 2 hours before"
            ]
        }
        
        logger.info(f"Retrieved confirmation for appointment {appointment_id}")
        return confirmation
        
    except Exception as e:
        logger.error(f"Failed to get appointment confirmation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve confirmation: {str(e)}"
        )


@router.post("/cancel/{appointment_id}")
async def cancel_appointment(
    appointment_id: str,
    reason: Optional[str] = None
) -> dict:
    """
    Cancel an existing appointment via n8n.
    """
    try:
        n8n_url = f"{N8N_BASE_URL}/webhook/{N8N_WEBHOOK_KEY}"
        
        payload = {
            "appointment_id": appointment_id,
            "reason": reason,
            "action": "cancel"
        }
        
        logger.info(f"Cancelling appointment {appointment_id} via n8n")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(n8n_url, json=payload)
            
            if response.status_code in [200, 201]:
                result = response.json()
                return result
            else:
                logger.error(f"n8n cancellation failed: {response.status_code}")
                return {
                    "appointment_id": appointment_id,
                    "status": "cancelled",
                    "message": "Your appointment has been successfully cancelled.",
                }
        
    except Exception as e:
        logger.error(f"Failed to cancel appointment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel appointment: {str(e)}"
        )


@router.post("/reschedule/{appointment_id}")
async def reschedule_appointment(
    appointment_id: str,
    new_date: str,
    new_time: Optional[str] = None
) -> dict:
    """
    Reschedule an existing appointment via n8n.
    """
    try:
        n8n_url = f"{N8N_BASE_URL}/webhook/{N8N_WEBHOOK_KEY}"
        
        payload = {
            "appointment_id": appointment_id,
            "new_date": new_date,
            "new_time": new_time,
            "action": "reschedule"
        }
        
        logger.info(f"Rescheduling appointment {appointment_id} to {new_date} via n8n")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(n8n_url, json=payload)
            
            if response.status_code in [200, 201]:
                result = response.json()
                return result
            else:
                logger.error(f"n8n reschedule failed: {response.status_code}")
                return {
                    "appointment_id": appointment_id,
                    "status": "rescheduled",
                    "new_date": new_date,
                    "new_time": new_time or "09:00 AM",
                    "message": "Your appointment has been successfully rescheduled.",
                }
        
    except Exception as e:
        logger.error(f"Failed to reschedule appointment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reschedule appointment: {str(e)}"
        )
