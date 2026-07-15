import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Dashboard } from './pages/Dashboard';
import { Incidents } from './pages/Incidents';
import { IncidentDetails } from './pages/IncidentDetails';
import { DependencyGraph } from './pages/DependencyGraph';
import { FixHistory } from './pages/FixHistory';
import { Settings } from './pages/Settings';
import { RemediationDashboard } from './pages/RemediationDashboard';
import { SLOPage } from './pages/SLO';
import { api } from './services/api';
import axios from 'axios';
import './App.css';

const client = axios.create({ baseURL: '' });

function App() {
  const [systemStatus, setSystemStatus] = useState<'healthy' | 'degraded'>('healthy');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    checkSystemHealth();
    const interval = setInterval(checkSystemHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const checkSystemHealth = async () => {
    try {
      await client.get('/health/live');
      setSystemStatus('healthy');
    } catch {
      setSystemStatus('degraded');
    }
  };

  const handleRefresh = () => {
    window.location.reload();
  };

  return (
    <BrowserRouter>
      <div className="app">
        <Header systemStatus={systemStatus} onRefresh={handleRefresh} onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)} />
        <div className="app-body">
          <Sidebar collapsed={sidebarCollapsed} />
          <main className={`main-content ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/incidents" element={<Incidents />} />
              <Route path="/incident/:id" element={<IncidentDetails />} />
              <Route path="/graph" element={<DependencyGraph />} />
              <Route path="/fixes" element={<FixHistory />} />
              <Route path="/remediation" element={
                <ErrorBoundary fallback={
                  <div style={{ padding: '2rem', color: '#e2e8f0' }}>
                    <h2>Remediation Page Temporarily Unavailable</h2>
                    <p>Please try again in a moment or return to the dashboard.</p>
                  </div>
                }>
                  <RemediationDashboard />
                </ErrorBoundary>
              } />
              <Route path="/settings" element={<Settings />} />
              <Route path="/slo" element={<SLOPage />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
