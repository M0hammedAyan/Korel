# Project Map

```
KORAL/
├── .ai/                          # AI Engineering Operating System (local only)
├── .github/                      # GitHub Actions CI/CD
├── agents/                       # K8s monitoring agents
│   ├── base_agent.py             # Base agent class
│   ├── cpu-agent/                # CPU metrics agent
│   ├── log-agent/                # Log parsing agent
│   ├── memory-agent/             # Memory metrics agent
│   └── storage-agent/            # Storage metrics agent
├── ai_engine/                    # LLM integration (GPT-4o, Claude)
├── AIML/                         # ML research & prototype code
│   └── Member1_work/
│       ├── ai_core/              # Core ML pipeline
│       └── koral_ai_ml/          # Compatibility package
├── alembic/                      # Database migrations
├── approval-engine/              # Human approval workflow
├── backend/                      # Core FastAPI application
├── charts/                       # Helm charts
├── correlation-engine/           # Event correlation
├── database/                     # SQL scripts
├── deploy/                       # Deployment scripts
├── docker/                       # Docker Compose configurations
├── docs/                         # Documentation
│   └── grafana/                  # Grafana dashboard JSONs
├── feedback/                     # ML feedback loop
├── frontend/                     # React/TypeScript/Vite UI
├── graphify-out/                 # Graphify analysis output
├── helm/                         # Additional Helm configs
├── infra/                        # Infrastructure scripts
├── k8s/                          # Kubernetes manifests
├── koral/                        # Python package source
├── koral_ai_ml/                  # AI/ML package
├── load_tests/                   # Locust load test scripts
├── notification/                 # Notification utilities
├── notifier/                     # Notification service
├── remediation-planner/          # Fix plan generation
├── requirements/                 # Python dependency files
├── sandbox-executor/             # Safe command execution
├── scripts/                      # Utility scripts
├── shared/                       # Shared libraries
├── system-intelligence-evaluation/
├── tests/                        # Integration & system tests
├── threshold/                    # Adaptive thresholding
└── verification-engine/          # Post-fix verification
```
