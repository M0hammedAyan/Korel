// vite.config.ts
import { defineConfig } from "file:///D:/CipherTECH/Projects/KORAL/frontend/node_modules/vite/dist/node/index.js";
import react from "file:///D:/CipherTECH/Projects/KORAL/frontend/node_modules/@vitejs/plugin-react/dist/index.js";
import { reticle } from "file:///D:/CipherTECH/Projects/KORAL/frontend/node_modules/@reticlehq/vite-plugin/dist/index.js";
var vite_config_default = defineConfig({
  plugins: [react(), reticle({ port: 4461 })],
  server: {
    port: 3e3,
    proxy: {
      "/api": {
        target: "http://localhost:8080",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, "")
      },
      "/ws": {
        target: "ws://localhost:8080",
        ws: true
      },
      "/anomalies": "http://localhost:8080",
      "/incidents": "http://localhost:8080",
      "/correlations": "http://localhost:8080",
      "/graph": "http://localhost:8080",
      "/fixes": "http://localhost:8080",
      "/remediation": "http://localhost:8080",
      "/slo": "http://localhost:8080",
      "/audit": "http://localhost:8080",
      "/users": "http://localhost:8080",
      "/tenants": "http://localhost:8080",
      "/health": "http://localhost:8080",
      "/metrics": "http://localhost:8080",
      "/ai": "http://localhost:8080",
      "/feedback": "http://localhost:8080"
    }
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom", "react-router-dom"],
          charts: ["recharts", "d3"]
        }
      }
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCJEOlxcXFxDaXBoZXJURUNIXFxcXFByb2plY3RzXFxcXEtPUkFMXFxcXGZyb250ZW5kXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ZpbGVuYW1lID0gXCJEOlxcXFxDaXBoZXJURUNIXFxcXFByb2plY3RzXFxcXEtPUkFMXFxcXGZyb250ZW5kXFxcXHZpdGUuY29uZmlnLnRzXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ltcG9ydF9tZXRhX3VybCA9IFwiZmlsZTovLy9EOi9DaXBoZXJURUNIL1Byb2plY3RzL0tPUkFML2Zyb250ZW5kL3ZpdGUuY29uZmlnLnRzXCI7aW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSAndml0ZSdcclxuaW1wb3J0IHJlYWN0IGZyb20gJ0B2aXRlanMvcGx1Z2luLXJlYWN0J1xyXG5pbXBvcnQgeyByZXRpY2xlIH0gZnJvbSAnQHJldGljbGVocS92aXRlLXBsdWdpbidcclxuXHJcbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZyh7XHJcbiAgcGx1Z2luczogW3JlYWN0KCksIHJldGljbGUoeyBwb3J0OiA0NDYxIH0pXSxcclxuICBzZXJ2ZXI6IHtcclxuICAgIHBvcnQ6IDMwMDAsXHJcbiAgICBwcm94eToge1xyXG4gICAgICAnL2FwaSc6IHtcclxuICAgICAgICB0YXJnZXQ6ICdodHRwOi8vbG9jYWxob3N0OjgwODAnLFxyXG4gICAgICAgIGNoYW5nZU9yaWdpbjogdHJ1ZSxcclxuICAgICAgICByZXdyaXRlOiAocGF0aCkgPT4gcGF0aC5yZXBsYWNlKC9eXFwvYXBpLywgJycpLFxyXG4gICAgICB9LFxyXG4gICAgICAnL3dzJzoge1xyXG4gICAgICAgIHRhcmdldDogJ3dzOi8vbG9jYWxob3N0OjgwODAnLFxyXG4gICAgICAgIHdzOiB0cnVlLFxyXG4gICAgICB9LFxyXG4gICAgICAnL2Fub21hbGllcyc6ICdodHRwOi8vbG9jYWxob3N0OjgwODAnLFxyXG4gICAgICAnL2luY2lkZW50cyc6ICdodHRwOi8vbG9jYWxob3N0OjgwODAnLFxyXG4gICAgICAnL2NvcnJlbGF0aW9ucyc6ICdodHRwOi8vbG9jYWxob3N0OjgwODAnLFxyXG4gICAgICAnL2dyYXBoJzogJ2h0dHA6Ly9sb2NhbGhvc3Q6ODA4MCcsXHJcbiAgICAgICcvZml4ZXMnOiAnaHR0cDovL2xvY2FsaG9zdDo4MDgwJyxcclxuICAgICAgJy9yZW1lZGlhdGlvbic6ICdodHRwOi8vbG9jYWxob3N0OjgwODAnLFxyXG4gICAgICAnL3Nsbyc6ICdodHRwOi8vbG9jYWxob3N0OjgwODAnLFxyXG4gICAgICAnL2F1ZGl0JzogJ2h0dHA6Ly9sb2NhbGhvc3Q6ODA4MCcsXHJcbiAgICAgICcvdXNlcnMnOiAnaHR0cDovL2xvY2FsaG9zdDo4MDgwJyxcclxuICAgICAgJy90ZW5hbnRzJzogJ2h0dHA6Ly9sb2NhbGhvc3Q6ODA4MCcsXHJcbiAgICAgICcvaGVhbHRoJzogJ2h0dHA6Ly9sb2NhbGhvc3Q6ODA4MCcsXHJcbiAgICAgICcvbWV0cmljcyc6ICdodHRwOi8vbG9jYWxob3N0OjgwODAnLFxyXG4gICAgICAnL2FpJzogJ2h0dHA6Ly9sb2NhbGhvc3Q6ODA4MCcsXHJcbiAgICAgICcvZmVlZGJhY2snOiAnaHR0cDovL2xvY2FsaG9zdDo4MDgwJyxcclxuICAgIH0sXHJcbiAgfSxcclxuICBidWlsZDoge1xyXG4gICAgb3V0RGlyOiAnZGlzdCcsXHJcbiAgICBzb3VyY2VtYXA6IGZhbHNlLFxyXG4gICAgcm9sbHVwT3B0aW9uczoge1xyXG4gICAgICBvdXRwdXQ6IHtcclxuICAgICAgICBtYW51YWxDaHVua3M6IHtcclxuICAgICAgICAgIHZlbmRvcjogWydyZWFjdCcsICdyZWFjdC1kb20nLCAncmVhY3Qtcm91dGVyLWRvbSddLFxyXG4gICAgICAgICAgY2hhcnRzOiBbJ3JlY2hhcnRzJywgJ2QzJ10sXHJcbiAgICAgICAgfSxcclxuICAgICAgfSxcclxuICAgIH0sXHJcbiAgfSxcclxufSlcclxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQUEyUyxTQUFTLG9CQUFvQjtBQUN4VSxPQUFPLFdBQVc7QUFDbEIsU0FBUyxlQUFlO0FBRXhCLElBQU8sc0JBQVEsYUFBYTtBQUFBLEVBQzFCLFNBQVMsQ0FBQyxNQUFNLEdBQUcsUUFBUSxFQUFFLE1BQU0sS0FBSyxDQUFDLENBQUM7QUFBQSxFQUMxQyxRQUFRO0FBQUEsSUFDTixNQUFNO0FBQUEsSUFDTixPQUFPO0FBQUEsTUFDTCxRQUFRO0FBQUEsUUFDTixRQUFRO0FBQUEsUUFDUixjQUFjO0FBQUEsUUFDZCxTQUFTLENBQUMsU0FBUyxLQUFLLFFBQVEsVUFBVSxFQUFFO0FBQUEsTUFDOUM7QUFBQSxNQUNBLE9BQU87QUFBQSxRQUNMLFFBQVE7QUFBQSxRQUNSLElBQUk7QUFBQSxNQUNOO0FBQUEsTUFDQSxjQUFjO0FBQUEsTUFDZCxjQUFjO0FBQUEsTUFDZCxpQkFBaUI7QUFBQSxNQUNqQixVQUFVO0FBQUEsTUFDVixVQUFVO0FBQUEsTUFDVixnQkFBZ0I7QUFBQSxNQUNoQixRQUFRO0FBQUEsTUFDUixVQUFVO0FBQUEsTUFDVixVQUFVO0FBQUEsTUFDVixZQUFZO0FBQUEsTUFDWixXQUFXO0FBQUEsTUFDWCxZQUFZO0FBQUEsTUFDWixPQUFPO0FBQUEsTUFDUCxhQUFhO0FBQUEsSUFDZjtBQUFBLEVBQ0Y7QUFBQSxFQUNBLE9BQU87QUFBQSxJQUNMLFFBQVE7QUFBQSxJQUNSLFdBQVc7QUFBQSxJQUNYLGVBQWU7QUFBQSxNQUNiLFFBQVE7QUFBQSxRQUNOLGNBQWM7QUFBQSxVQUNaLFFBQVEsQ0FBQyxTQUFTLGFBQWEsa0JBQWtCO0FBQUEsVUFDakQsUUFBUSxDQUFDLFlBQVksSUFBSTtBQUFBLFFBQzNCO0FBQUEsTUFDRjtBQUFBLElBQ0Y7QUFBQSxFQUNGO0FBQ0YsQ0FBQzsiLAogICJuYW1lcyI6IFtdCn0K
