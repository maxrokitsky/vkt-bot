"""
Example script to test VKT Bot API.

Usage:
    python examples/test_api.py
"""

import requests

# Configuration
BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "your-password-here"


def test_api():
    """Test API endpoints."""
    session = requests.Session()

    print("=" * 60)
    print("VKT Bot API Test")
    print("=" * 60)

    # 1. Login
    print("\n1. Testing login...")
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
    )

    if response.status_code != 200:
        print(f"❌ Login failed: {response.json()}")
        return

    token = response.json()["access_token"]
    print(f"✅ Login successful! Token: {token[:20]}...")

    # Set authorization header
    session.headers.update({"Authorization": f"Bearer {token}"})

    # 2. Get current user
    print("\n2. Getting current user info...")
    response = session.get(f"{BASE_URL}/api/auth/me")
    if response.status_code == 200:
        user = response.json()
        print(f"✅ Current user: {user['username']}")
        print(f"   Email: {user['email']}")
        print(f"   Is admin: {user['is_superuser']}")
    else:
        print(f"❌ Failed: {response.json()}")

    # 3. List users
    print("\n3. Listing users...")
    response = session.get(f"{BASE_URL}/api/users")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['total']} users (page {data['page']}/{data['pages']})")
        for user in data["items"]:
            print(
                f"   - {user['username']} ({'admin' if user['is_superuser'] else 'user'})"
            )
    else:
        print(f"❌ Failed: {response.json()}")

    # 4. List chats
    print("\n4. Listing chats...")
    response = session.get(f"{BASE_URL}/api/chats")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['total']} chats")
        for chat in data["items"][:5]:  # Show first 5
            print(f"   - {chat['id']}: {chat.get('title', 'N/A')}")
    else:
        print(f"❌ Failed: {response.json()}")

    # 5. List roles
    print("\n5. Listing roles...")
    response = session.get(f"{BASE_URL}/api/roles")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['total']} roles")
        for role in data["items"]:
            print(f"   - {role['name']} (ID: {role['id']})")
    else:
        print(f"❌ Failed: {response.json()}")

    # 6. Create a test role
    print("\n6. Creating test role...")
    response = session.post(
        f"{BASE_URL}/api/roles",
        json={"name": "Test Role"},
    )
    if response.status_code == 201:
        role = response.json()
        print(f"✅ Created role: {role['name']} (ID: {role['id']})")

        # 7. Get role with members
        print("\n7. Getting role details...")
        response = session.get(f"{BASE_URL}/api/roles/{role['id']}")
        if response.status_code == 200:
            role_data = response.json()
            print(f"✅ Role: {role_data['name']}")
            print(f"   Members: {len(role_data['members'])}")

        # 8. Delete test role
        print("\n8. Deleting test role...")
        response = session.delete(f"{BASE_URL}/api/roles/{role['id']}")
        if response.status_code == 204:
            print("✅ Role deleted successfully")
        else:
            print(f"❌ Failed to delete: {response.json()}")
    elif response.status_code == 400:
        print(f"⚠️  Role might already exist: {response.json()}")
    else:
        print(f"❌ Failed: {response.json()}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_api()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to API server.")
        print("   Make sure the server is running: uv run server")
    except Exception as e:
        print(f"❌ Error: {e}")
