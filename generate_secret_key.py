import secrets

# Generate a secure secret key
secret_key = secrets.token_hex(32)
print(f"SECRET_KEY={secret_key}")
print(f"\nUse this as your SECRET_KEY in Render:")
print(f"{secret_key}")
