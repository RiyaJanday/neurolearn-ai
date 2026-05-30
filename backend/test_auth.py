from core.auth_utils import (
    hash_password, verify_password,
    create_access_token, decode_token,
    generate_otp, hash_otp, verify_otp_hash,
    generate_totp_secret, generate_backup_codes
)

# Test password hashing
hashed = hash_password("mypassword123")
print("Password hash:", hashed[:30], "...")
print("Verify correct:", verify_password("mypassword123", hashed))
print("Verify wrong:  ", verify_password("wrongpassword", hashed))

# Test JWT
token = create_access_token({"sub": "user-123"})
decoded = decode_token(token)
print("\nJWT token created:", token[:40], "...")
print("Decoded sub:", decoded["sub"])
print("Token type:", decoded["type"])

# Test OTP
otp = generate_otp()
otp_hash = hash_otp(otp)
print("\nGenerated OTP:", otp)
print("OTP verify correct:", verify_otp_hash(otp, otp_hash))
print("OTP verify wrong:  ", verify_otp_hash("000000", otp_hash))

# Test TOTP
secret = generate_totp_secret()
print("\nTOTP secret:", secret)

# Test backup codes
codes = generate_backup_codes()
print("\nBackup codes:", codes)

print("\n✅ All auth utilities working!")