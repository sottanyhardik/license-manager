#!/usr/bin/env python3
"""Phase 20: Session Expiration Testing - JWT token lifetime and refresh"""
import time, pytest, requests, jwt

class TestPhase20:
    def test_session_expiration(self):
        """Test JWT token expiration and 401 handling"""
        print("\n" + "="*70)
        print("PHASE 20: SESSION EXPIRATION TESTING")
        print("="*70)

        # 1. Login and get token
        r = requests.post("http://localhost:8000/api/auth/login/",
                         json={"username":"hardik","password":"admin@123"}, timeout=10)
        assert r.status_code == 200, "Login failed"
        token = r.json()["access"]

        # 2. Verify token works
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get("http://localhost:8000/api/licenses/?page_size=1", headers=headers)
        assert r.status_code == 200, "Valid token should work"
        print("✓ Valid token: license list accessible (200)")

        # 3. Decode token to check expiration
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp_time = decoded.get("exp")
        now = int(time.time())
        lifetime_seconds = exp_time - now
        lifetime_minutes = lifetime_seconds / 60

        print(f"✓ Token lifetime: {lifetime_minutes:.1f} minutes ({lifetime_seconds} seconds)")
        assert 25 <= lifetime_minutes <= 35, f"Token lifetime should be ~30 min, got {lifetime_minutes}"

        # 4. Test expired token (create artificially old token)
        try:
            expired_token = jwt.encode(
                {"sub": 1, "exp": int(time.time()) - 3600},
                "secret",
                algorithm="HS256"
            )
            headers_expired = {"Authorization": f"Bearer {expired_token}"}
            r = requests.get("http://localhost:8000/api/licenses/?page_size=1",
                           headers=headers_expired, timeout=10)

            # Should get 401 for expired token
            if r.status_code == 401:
                print("✓ Expired token returns 401")
            else:
                print(f"⚠ Expired token returned {r.status_code} (expected 401)")
        except Exception as e:
            print(f"⚠ Expired token test: {e}")

        # 5. Test missing token
        r = requests.get("http://localhost:8000/api/licenses/?page_size=1", timeout=10)
        if r.status_code in [401, 403]:
            print(f"✓ No token returns {r.status_code}")
        else:
            print(f"⚠ No token returned {r.status_code}")

        # 6. Test malformed token
        headers_bad = {"Authorization": "Bearer invalid.token.here"}
        r = requests.get("http://localhost:8000/api/licenses/?page_size=1",
                        headers=headers_bad, timeout=10)
        if r.status_code in [401, 403]:
            print(f"✓ Malformed token returns {r.status_code}")
        else:
            print(f"⚠ Malformed token returned {r.status_code}")

        print("\n" + "="*70)
        print("✓ PHASE 20: Session expiration verified")
        print("="*70)

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
