import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { GoogleOAuthProvider } from '@react-oauth/google'
import HyderabadMapPage from './pages/HyderabadMapPage'
import RealEstateDashboard from './pages/RealEstateDashboard'
import StoryLanding from './pages/StoryLanding'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID

function ProtectedRoute({ children }) {
  const user = sessionStorage.getItem('fyp_user')
  if (!user) return <Navigate to="/" replace />
  return children
}

function App() {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<StoryLanding />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <RealEstateDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/explore"
            element={
              <ProtectedRoute>
                <HyderabadMapPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </GoogleOAuthProvider>
  )
}

export default App
