"""
Health data models for API request/response validation.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class ActivitySummary(BaseModel):
    """Activity and step count summary"""
    daily_averages: Optional[Dict[str, Any]] = None
    daily_ranges: Optional[Dict[str, Any]] = None
    weekly_averages: Optional[Dict[str, Any]] = None
    activity_patterns: Optional[Dict[str, Any]] = None

class SleepSummary(BaseModel):
    """Sleep data summary"""
    sleep_sessions: Optional[List[Dict[str, Any]]] = None
    sleep_quality: Optional[Dict[str, Any]] = None
    sleep_patterns: Optional[Dict[str, Any]] = None

class HeartRateSummary(BaseModel):
    """Heart rate data summary"""
    resting_hr: Optional[float] = None
    average_hr: Optional[float] = None
    hr_ranges: Optional[Dict[str, Any]] = None
    measurements: Optional[List[Dict[str, Any]]] = None

class HRVSummary(BaseModel):
    """HRV (Heart Rate Variability) summary"""
    average_hrv: Optional[float] = None
    hrv_trend: Optional[str] = None
    measurements: Optional[List[Dict[str, Any]]] = None

class ExerciseSummary(BaseModel):
    """Exercise and workout data summary"""
    sessions: Optional[List[Dict[str, Any]]] = None
    total_sessions: Optional[int] = None
    exercise_types: Optional[List[str]] = None
    performance_metrics: Optional[Dict[str, Any]] = None

class UserProfile(BaseModel):
    """User profile and demographic data"""
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    location: Optional[Dict[str, Any]] = None
    medical_history: Optional[Dict[str, Any]] = None
    lifestyle_preferences: Optional[Dict[str, Any]] = None
    goals: Optional[Dict[str, Any]] = None

class HealthData(BaseModel):
    """Complete health data payload from mobile app"""
    activity_summary_for_llm: Optional[ActivitySummary] = None
    sleep_summary_for_llm: Optional[SleepSummary] = None
    heart_rate_summary_for_llm: Optional[HeartRateSummary] = None
    hrv_summary_for_llm: Optional[HRVSummary] = None
    exercise_summary_for_llm: Optional[ExerciseSummary] = None
    user_data: Optional[UserProfile] = None
