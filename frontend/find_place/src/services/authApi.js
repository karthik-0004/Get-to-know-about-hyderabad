const API_BASE = `${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api`

export async function registerUser({ username, email, password }) {
  const res = await fetch(`${API_BASE}/register/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password }),
  })

  const data = await res.json().catch(() => null)

  if (!res.ok) {
    throw new Error(data?.error || 'Registration failed')
  }
  return data
}

export async function loginUser({ identifier, password }) {
  const res = await fetch(`${API_BASE}/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier, password }),
  })

  const data = await res.json().catch(() => null)

  if (!res.ok) {
    throw new Error(data?.error || 'Login failed')
  }
  return data
}

export async function googleLogin(credential) {
  const res = await fetch(`${API_BASE}/google-login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential }),
  })

  const data = await res.json().catch(() => null)

  if (!res.ok) {
    throw new Error(data?.error || 'Google login failed')
  }
  return data
}
