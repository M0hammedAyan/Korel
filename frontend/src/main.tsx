import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

if (import.meta.env.DEV) import('./reticle-dev')

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
)

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
