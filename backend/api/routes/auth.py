from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel, EmailStr

from db.database import get_db
from db.models import User, OTPCode, UserSession, BackupCode
from core.auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    generate_otp,
    hash_otp,
    verify_otp_hash,
    generate_totp_secret,
    get_totp_uri,
    verify_totp,
    generate_backup_codes,
    hash_backup_code,
)

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_fp: Optional[str] = None
    device_name: Optional[str] = None


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    code: str
    purpose: str  # register | login | device | reset


class ProfileRequest(BaseModel):
    exam_target: str
    subjects: list
    study_hours: str
    exam_date: Optional[str] = None


class TOTPVerifyRequest(BaseModel):
    code: str


class RefreshRequest(BaseModel):
    refresh_token: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def create_otp_record(db: Session, email: str, purpose: str) -> str:
    """Invalidate old OTPs for this email+purpose, create a new one."""
    db.query(OTPCode).filter(
        OTPCode.email == email,
        OTPCode.purpose == purpose,
        OTPCode.used == False,
    ).update({"used": True})

    code = generate_otp()
    otp = OTPCode(
        email=email,
        code_hash=hash_otp(code),
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(otp)
    db.commit()
    return code


def verify_otp_record(db: Session, email: str, code: str, purpose: str) -> bool:
    """Find latest unused OTP, check expiry and hash."""
    otp = (
        db.query(OTPCode)
        .filter(
            OTPCode.email == email,
            OTPCode.purpose == purpose,
            OTPCode.used == False,
        )
        .order_by(OTPCode.created_at.desc())
        .first()
    )

    if not otp:
        return False
    if otp.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return False
    if not verify_otp_hash(code, otp.code_hash):
        return False

    otp.used = True
    db.commit()
    return True


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # Check if email already exists
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(req.password) < 6:
        raise HTTPException(
            status_code=400, detail="Password must be at least 6 characters"
        )

    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        first_name=req.first_name,
        last_name=req.last_name,
        is_verified=False,
    )
    db.add(user)
    db.commit()

    code = create_otp_record(db, req.email, "register")

    print(f"\n📧 OTP for {req.email}: {code}\n")

    return {
        "message": "Registration successful. OTP sent to email.",
        "demo_otp": code,
    }


@router.post("/verify-otp")
def verify_otp(req: OTPVerifyRequest, db: Session = Depends(get_db)):
    if not verify_otp_record(db, req.email, req.code, req.purpose):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    if req.purpose == "register":
        user = db.query(User).filter(User.email == req.email).first()
        if user:
            user.is_verified = True
            db.commit()
        return {"message": "Email verified", "next": "profile"}

    if req.purpose in ["login", "device"]:
        user = db.query(User).filter(User.email == req.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        access_token = create_access_token({"sub": user.id})
        refresh_token = create_refresh_token({"sub": user.id})

        # Save session
        session = UserSession(
            user_id=user.id,
            refresh_token_hash=hash_token(refresh_token),
            is_active=True,
        )
        db.add(session)
        db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "onboarding_complete": user.onboarding_complete,
                "totp_enabled": user.totp_enabled,
            },
        }

    return {"message": "OTP verified"}


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_verified:
        raise HTTPException(status_code=401, detail="Please verify your email first")

    known_fps = [s.device_fp for s in user.sessions if s.is_active and s.device_fp]
    is_new_device = req.device_fp and req.device_fp not in known_fps

    if is_new_device:
        code = create_otp_record(db, req.email, "device")
        print(f"\n🔐 Device OTP for {req.email}: {code}\n")
        return {
            "requires_device_otp": True,
            "demo_otp": code,
        }

    if user.totp_enabled:
        return {"requires_totp": True}

    access_token = create_access_token({"sub": user.id})
    refresh_token = create_refresh_token({"sub": user.id})

    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        device_name=req.device_name,
        device_fp=req.device_fp,
        is_active=True,
    )
    db.add(session)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "onboarding_complete": user.onboarding_complete,
            "totp_enabled": user.totp_enabled,
        },
    }


@router.post("/refresh")
def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_hash = hash_token(req.refresh_token)
    session = (
        db.query(UserSession)
        .filter(
            UserSession.refresh_token_hash == token_hash,
            UserSession.is_active == True,
        )
        .first()
    )

    if not session:
        raise HTTPException(status_code=401, detail="Session expired or revoked")

    new_access = create_access_token({"sub": payload["sub"]})
    new_refresh = create_refresh_token({"sub": payload["sub"]})

    session.refresh_token_hash = hash_token(new_refresh)
    session.last_seen = datetime.now(timezone.utc)
    db.commit()

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
    }


@router.post("/profile")
def update_profile(
    req: ProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.exam_target = req.exam_target
    user.subjects = req.subjects
    user.study_hours = req.study_hours
    user.exam_date = req.exam_date
    user.onboarding_complete = True
    db.commit()
    return {"message": "Profile saved successfully"}


@router.post("/totp/setup")
def setup_totp(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, user.email)
    user.totp_secret = secret
    db.commit()
    return {"secret": secret, "uri": uri}


@router.post("/totp/enable")
def enable_totp(
    req: TOTPVerifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="Call /totp/setup first")
    if not verify_totp(user.totp_secret, req.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    user.totp_enabled = True
    db.commit()

    codes = generate_backup_codes()
    for c in codes:
        bc = BackupCode(user_id=user.id, code_hash=hash_backup_code(c))
        db.add(bc)
    db.commit()

    return {"message": "2FA enabled", "backup_codes": codes}


@router.get("/sessions")
def get_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user.id,
            UserSession.is_active == True,
        )
        .all()
    )
    return [
        {
            "id": s.id,
            "device_name": s.device_name,
            "location": s.location,
            "last_seen": s.last_seen,
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(UserSession)
        .filter(
            UserSession.id == session_id,
            UserSession.user_id == user.id,
        )
        .first()
    )
    if session:
        session.is_active = False
        db.commit()
    return {"message": "Session revoked"}


@router.delete("/sessions")
def revoke_all_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(UserSession).filter(UserSession.user_id == user.id).update(
        {"is_active": False}
    )
    db.commit()
    return {"message": "All sessions revoked"}


@router.post("/forgot-password")
def forgot_password(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if user:
        code = create_otp_record(db, email, "reset")
        print(f"\n🔑 Password reset OTP for {email}: {code}\n")
    return {"message": "If that email exists, a reset code was sent"}


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "totp_enabled": user.totp_enabled,
        "onboarding_complete": user.onboarding_complete,
        "exam_target": user.exam_target,
        "subjects": user.subjects,
        "study_hours": user.study_hours,
    }
