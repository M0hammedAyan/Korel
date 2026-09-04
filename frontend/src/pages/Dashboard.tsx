import React, { useState, useEffect, useCallback, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api, wsService } from '../services/api';
import { Incident, Anomaly } from '../types';
import { AIAssistant } from '../components/AIAssistant';
import '../styles/Dashboard.enterprise.css';

interface ChartPoint {
  timestamp: number;
  value: number;
  z_score: number;
  anomaly: boolean;
}

// Live clock hook
function useLiveClock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return time;
}

const formatTime = (date: Date) => {
  return date.toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit',
    hour12: false 
  });
};

const formatTimestamp = (ts: number) => {
  const now = Date.now();
  const diff = Math.floor((now - ts) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
};

const formatXAxis = (ts: number) => {
  const d = new Date(ts * 1000);
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
};

export const Dashboard: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [cpuData, setCpuData] = useState<ChartPoint[]>([]);
  const [memoryData, setMemoryData] = useState<ChartPoint[]>([]);
  const [storageData, setStorageData] = useState<ChartPoint[]>([]);
  const [wsStatus, setWsStatus] = useState<'connecting' | 'live' | 'reconnecting'>('connecting');
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const now = useLiveClock();

  const buildCharts = useCallback((data: Anomaly[]) => {
    const toPoints = (metric: string): ChartPoint[] =>
      data
        .filter(a => a?.metric === metric)
        .slice(-40)
        .map(a => ({
          timestamp: a.timestamp,
          value: parseFloat(a.value.toFixed(2)),
          z_score: parseFloat(a.z_score.toFixed(2)),
          anomaly: a.is_anomaly,
        }));

    setCpuData(toPoints('cpu'));
    setMemoryData(toPoints('memory'));
    setStorageData(toPoints('storage'));
  }, []);

  const loadData = useCallback(async () => {
    try {
      const [inc, anoms] = await Promise.all([api.getIncidents(), api.getAnomalies()]);
      setIncidents(inc || []);
      setAnomalies(anoms || []);
      buildCharts(anoms || []);
      setLastUpdate(new Date());
    } catch (err) {
      console.error('Load error:', err);
    }
  }, [buildCharts]);

  useEffect(() => {
    loadData();

    wsService.connect(
      () => setWsStatus('live'),
      () => setWsStatus('reconnecting'),
    );

    wsService.subscribe((msg: any) => {
      if (!msg?.type || !msg?.payload) return;

      if (msg.type === 'anomaly') {
        setAnomalies(prev => {
          const updated = [...prev, msg.payload];
          buildCharts(updated);
          return updated;
        });
        setLastUpdate(new Date());
      }

      if (msg.type === 'incident' || msg.type === 'incident_ai') {
        setIncidents(prev => {
          const idx = prev.findIndex(i => i.incident_id === msg.payload.incident_id);
          if (idx >= 0) {
            const updated = [...prev];
            updated[idx] = { ...updated[idx], ...msg.payload };
            return updated;
          }
          return [msg.payload, ...prev];
        });
        setLastUpdate(new Date());
      }
    });

    const interval = setInterval(loadData, 30000);
    return () => { 
      clearInterval(interval); 
      wsService.disconnect(); 
    };
  }, [loadData, buildCharts]);

  const latestCpu = anomalies.filter(a => a?.metric === 'cpu').slice(-1)[0];
  const latestMem = anomalies.filter(a => a?.metric === 'memory').slice(-1)[0];
  const latestStor = anomalies.filter(a => a?.metric === 'storage').slice(-1)[0];
  const cpuVal = latestCpu ? parseFloat(latestCpu.value.toFixed(1)) : 0;
  const memVal = latestMem ? parseFloat(latestMem.value.toFixed(0)) : 0;   // raw MB
  const storVal = latestStor ? parseFloat(latestStor.value.toFixed(1)) : 0; // raw KB/s

  const severityColor = (sev: string) => {
    switch (sev) {
      case 'critical': return '#ef4444';
      case 'high': return '#f97316';
      case 'medium': return '#eab308';
      default: return '#10b981';
    }
  };

  return (
    <div className="dashboard-enterprise">
      {/* TOP BAR */}
      <div className="dashboard-topbar-enterprise">
        <div className="topbar-left">
          <div className="live-status">
            <span className={`live-dot ${wsStatus}`}></span>
            <span className="live-label">
              {wsStatus === 'live' ? 'LIVE' : 'RECONNECTING'}
            </span>
          </div>
          <span className="topbar-divider">|</span>
          <div className="clock-display">{formatTime(now)}</div>
          {lastUpdate && (
            <>
              <span className="topbar-divider">|</span>
              <div className="last-update-display">Updated: {formatTime(lastUpdate)}</div>
            </>
          )}
        </div>
      </div>

      <div className="dashboard-container-enterprise">
        {/* LEFT: CHARTS AND INCIDENTS */}
        <div className="dashboard-main">
          {/* 3 GRAPHS ROW */}
          <div className="graphs-row">
            {/* CPU USAGE */}
            <div className="graph-card">
              <div className="graph-header">
                <span className="graph-title">CPU Usage</span>
                <span className="graph-value" style={{ color: cpuVal > 80 ? '#ef4444' : cpuVal > 50 ? '#f97316' : '#10b981' }}>
                  {cpuVal}%
                </span>
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={cpuData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
                  <XAxis dataKey="timestamp" stroke="#718096" tick={{ fontSize: 10 }} tickFormatter={formatXAxis} interval="preserveStartEnd" />
                  <YAxis stroke="#718096" tick={{ fontSize: 11 }} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1a202c', border: '1px solid #4a5568', borderRadius: '6px', color: '#e2e8f0', fontSize: '12px' }} 
                    formatter={(value: any) => [`${value}%`, 'CPU Usage']}
                  />
                  <Line type="monotone" dataKey="value" stroke="#3b82f6" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* MEMORY USAGE */}
            <div className="graph-card">
              <div className="graph-header">
                <span className="graph-title">Memory Usage</span>
                <span className="graph-value" style={{ color: memVal > 12000 ? '#ef4444' : memVal > 8000 ? '#f97316' : '#10b981' }}>
                  {memVal} MB
                </span>
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={memoryData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
                  <XAxis dataKey="timestamp" stroke="#718096" tick={{ fontSize: 10 }} tickFormatter={formatXAxis} interval="preserveStartEnd" />
                  <YAxis stroke="#718096" tick={{ fontSize: 11 }} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1a202c', border: '1px solid #4a5568', borderRadius: '6px', color: '#e2e8f0', fontSize: '12px' }} 
                    formatter={(value: any) => [`${value} MB`, 'Memory']}
                  />
                  <Line type="monotone" dataKey="value" stroke="#8b5cf6" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* STORAGE I/O */}
            <div className="graph-card">
              <div className="graph-header">
                <span className="graph-title">Storage I/O</span>
                <span className="graph-value" style={{ color: storVal > 500 ? '#ef4444' : storVal > 300 ? '#f97316' : '#10b981' }}>
                  {storVal} KB/s
                </span>
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={storageData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
                  <XAxis dataKey="timestamp" stroke="#718096" tick={{ fontSize: 10 }} tickFormatter={formatXAxis} interval="preserveStartEnd" />
                  <YAxis stroke="#718096" tick={{ fontSize: 11 }} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1a202c', border: '1px solid #4a5568', borderRadius: '6px', color: '#e2e8f0', fontSize: '12px' }} 
                    formatter={(value: any) => [`${value} KB/s`, 'Storage I/O']}
                  />
                  <Line type="monotone" dataKey="value" stroke="#06b6d4" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* INCIDENTS PANEL */}
          <div className="incidents-panel-enterprise">
            <div className="panel-header">
              <span className="panel-title">Active Incidents</span>
              <span className="incident-count">{incidents.length}</span>
            </div>
            <div className="incidents-list-enterprise">
              {incidents.length === 0 ? (
                <div className="empty-message">No active incidents</div>
              ) : (
                incidents.slice(0, 6).map(inc => (
                  <div key={inc.incident_id} className="incident-row">
                    <div className="incident-severity" style={{ borderLeftColor: severityColor(inc.severity) }}></div>
                    <div className="incident-info">
                      <div className="incident-name">{inc.affected_pods?.[0] || inc.namespace || 'System'}</div>
                      <div className="incident-detail">{inc.summary || inc.namespace}</div>
                      {inc.ai_explanation && (
                        <div className="incident-ai-explanation" style={{ fontSize: '11px', color: '#a0aec0', marginTop: '3px', fontStyle: 'italic' }}>
                          🤖 {inc.ai_explanation}
                        </div>
                      )}
                    </div>
                    <div className="incident-meta">
                      <span className="incident-badge" style={{ backgroundColor: severityColor(inc.severity) + '20', color: severityColor(inc.severity) }}>
                        {inc.severity?.toUpperCase() || 'INFO'}
                      </span>
                      <span className="incident-time">{formatTimestamp(inc.timestamp)}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* RIGHT: AI CHAT */}
        <div className="dashboard-sidebar-enterprise">
          <AIAssistant />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
