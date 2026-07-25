from auth import create_access_token

token = create_access_token(
    {"sub": "prashanth@gmail.com"}
)

print(token)