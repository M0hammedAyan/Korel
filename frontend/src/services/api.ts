import axios from 'axios';
import { Incident, Graph, Anomaly, SLOData } from '../types';

const API_KEY = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_KEY) || '';

const client = axios.create({
  baseURL: '',
  headers: API_KEY ? { 'X-API-Key': API_KEY } : {},
});

export const api = {
  getIncidents: async (): Promise<Incident[]> => {
    try {
      const { data } = await client.get('/incidents');
      return Array.isArray(data) ? data : [];
    } catch (e) {
      console.error('[KORAL] /incidents failed:', e);
      return [];
    }
  },

  getGraph: async (): Promise<Graph> => {
    try {
      const { data } = await client.get('/graph');
      return data?.nodes ? data : { nodes: [], edges: [] };
    } catch (e) {
      console.error('[KORAL] /graph failed:', e);
      return { nodes: [], edges: [] };
    }
  },

  getAnomalies: async (): Promise<Anomaly[]> => {
    try {
      const { data } = await client.get('/anomalies');
      return Array.isArray(data) ? data : [];
    } catch (e) {
      console.error('[KORAL] /anomalies failed:', e);
      return [];
    }
  },

  getIncidentById: async (id: string): Promise<Incident | null> => {
    const incidents = await api.getIncidents();
    return incidents.find(i => i.incident_id === id) ?? null;
  },

  getAIActivity: async (): Promise<any[]> => {
    try {
      const { data } = await client.get('/ai/activity?limit=50');
      return Array.isArray(data) ? data : [];
    } catch { return []; }
  },

  aiChat: async (message: string, context?: any): Promise<any> => {
    try {
      const { data } = await client.post('/ai/chat', { message, context });
      return data;
    } catch { return { response: 'AI unavailable', model: 'none', timestamp: new Date().toISOString() }; }
  },

  getFixHistory: async (limit: number = 100, appliedBy?: string): Promise<any[]> => {
    try {
      const params = appliedBy ? { limit, applied_by: appliedBy } : { limit };
      const { data } = await client.get('/fixes/history', { params });
      return Array.isArray(data) ? data : [];
    } catch (e) {
      console.error('[KORAL] /fixes/history failed:', e);
      return [];
    }
  },

  getFixStats: async (): Promise<any> => {
    try {
      const { data } = await client.get('/fixes/stats');
      return data;
    } catch (e) {
      console.error('[KORAL] /fixes/stats failed:', e);
      return { total_fixes: 0, ai_fixes: 0, developer_fixes: 0, successful_fixes: 0, failed_fixes: 0, success_rate: 0 };
    }
  },

  recordFix: async (fix: any): Promise<any> => {
    try {
      const { data } = await client.post('/fixes/record', fix);
      return data;
    } catch (e) {
      console.error('[KORAL] /fixes/record failed:', e);
      throw e;
    }
  },

  getSLO: async (): Promise<SLOData | null> => {
    try {
      const { data } = await client.get('/slo/');
      return data;
    } catch (e) {
      console.error('[KORAL] /slo/ failed:', e);
      return null;
    }
  },

  correlateBatch: async (events: any[], windowSeconds: number = 60): Promise<any> => {
    try {
      const { data } = await client.post('/correlate-batch', { events, window_seconds: windowSeconds });
      return data;
    } catch (e) {
      console.error('[KORAL] /correlate-batch failed:', e);
      return { incidents: [], count: 0 };
    }
  },
};

export class WebSocketService {
  private ws: WebSocket | null = null;
  private listeners: ((data: any) => void)[] = [];
  private onOpenCb?: () => void;
  private onCloseCb?: () => void;

  connect(onOpen?: () => void, onClose?: () => void) {
    this.onOpenCb  = onOpen;
    this.onCloseCb = onClose;
    this._connect();
  }

  private _connect() {
    try {
      // In dev (npm start), CRA proxy does not support WebSocket.
      // Connect directly to backend port 8080.
      // In production (nginx), use the same host which proxies /ws/ to backend.
      const isDev = window.location.port === '3000';
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const host  = isDev ? 'localhost:8000' : window.location.host;
      const wsUrl = `${proto}://${host}/ws/live?api_key=koral-dev-api-key-2024`;
      this.ws = new WebSocket(wsUrl);
      this.ws.onopen  = () => { console.log('[KORAL] WS connected to', wsUrl); this.onOpenCb?.(); };
      this.ws.onclose = () => { console.log('[KORAL] WS closed'); this.onCloseCb?.(); setTimeout(() => this._connect(), 5000); };
      this.ws.onmessage = (e) => {
        try { this.listeners.forEach(l => l(JSON.parse(e.data))); } catch {}
      };
      this.ws.onerror = () => {
        this.onCloseCb?.();
      };
    } catch (e) {
      console.warn('[KORAL] WS init failed:', e);
    }
  }

  subscribe(cb: (data: any) => void) { this.listeners.push(cb); }
  disconnect() { this.ws?.close(); }
}

export const wsService = new WebSocketService();
