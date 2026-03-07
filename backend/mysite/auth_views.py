import json
import uuid

import requests as http_requests
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def register_user(request):
    """Register a new user with username, email, and password."""
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""

    if not username or not email or not password:
        return JsonResponse(
            {"error": "username, email, and password are required"}, status=400
        )

    if len(password) < 6:
        return JsonResponse(
            {"error": "Password must be at least 6 characters"}, status=400
        )

    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "Username already taken"}, status=409)

    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already registered"}, status=409)

    user = User.objects.create_user(
        username=username, email=email, password=password
    )

    return JsonResponse(
        {
            "message": "Registration successful",
            "user": {"id": user.id, "username": user.username, "email": user.email},
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def login_user(request):
    """Authenticate a user with email/username and password."""
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    identifier = (payload.get("identifier") or "").strip()
    password = payload.get("password") or ""

    if not identifier or not password:
        return JsonResponse(
            {"error": "identifier and password are required"}, status=400
        )

    # Allow login by email or username
    user = None
    if "@" in identifier:
        try:
            user_obj = User.objects.get(email=identifier)
            user = authenticate(username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None
    else:
        user = authenticate(username=identifier, password=password)

    if user is None:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    return JsonResponse(
        {
            "message": "Login successful",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
        },
        status=200,
    )


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def google_login(request):
    """Authenticate or register a user via Google One Tap / Sign-In."""
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    credential = (payload.get("credential") or "").strip()
    if not credential:
        return JsonResponse({"error": "Google credential is required"}, status=400)

    # Verify the ID token with Google
    try:
        resp = http_requests.get(
            GOOGLE_TOKEN_INFO_URL,
            params={"id_token": credential},
            timeout=10,
        )
        if resp.status_code != 200:
            return JsonResponse({"error": "Invalid Google token"}, status=401)
        google_data = resp.json()
    except http_requests.RequestException:
        return JsonResponse({"error": "Could not verify Google token"}, status=502)

    email = google_data.get("email", "").strip()
    if not email or google_data.get("email_verified") != "true":
        return JsonResponse({"error": "Google email not verified"}, status=401)

    name = google_data.get("name", "").strip()

    # Get or create the user
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Create a new account for this Google user
        base_username = email.split("@")[0]
        username = base_username
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{uuid.uuid4().hex[:6]}"
        user = User.objects.create_user(
            username=username,
            email=email,
            password=None,  # No password — Google-only account
        )
        if name:
            parts = name.split(" ", 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
            user.save(update_fields=["first_name", "last_name"])

    return JsonResponse(
        {
            "message": "Google login successful",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
        },
        status=200,
    )
