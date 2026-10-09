import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import StaffApp from './StaffApp'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode>{window.location.pathname.startsWith('/staff') ? <StaffApp /> : <App />}</React.StrictMode>)
