# Research Document

## Section 5.1: Visualizations

### Figure 1: Circularity Rate
<div align="center">
```mermaid
graph TD;
    A[Baseline: 0.630] -->|Red| A1[0.630]
    B[DialogueEngine/Seed: 0.097] -->|Green| B1[0.097]
    C[Fixy Interventions: 0.409] -->|Yellow| C1[0.409]
    D[Dream/Energy: 0.421] -->|Yellow| D1[0.421]
```
</div>

### Figure 2: Progress Rate
<div align="center">
```mermaid
graph TD;
    A[Baseline: 0.414] -->|Yellow| A1[0.414]
    B[DialogueEngine/Seed: 1.000] -->|Green| B1[1.000]
    C[Fixy Interventions: 0.517] -->|Blue| C1[0.517]
    D[Dream/Energy: 0.517] -->|Blue| D1[0.517]
```
</div>

### Figure 3: Intervention Utility
<div align="center">
```mermaid
graph TD;
    A[Baseline: 0.000] -->|Gray| A1[0.000]
    B[DialogueEngine/Seed: 0.000] -->|Gray| B1[0.000]
    C[Fixy Interventions: 0.333] -->|Blue| C1[0.333]
    D[Dream/Energy: 0.000] -->|Gray| D1[0.000]
```
</div>

### Figure 4: All Metrics
<div align="center">
| Intervention           | Performance Indicator |
|------------------------|----------------------|
| Baseline               | 🔴                   |
| DialogueEngine/Seed    | 🟢                   |
| Fixy Interventions      | 🔵                   |
| Dream/Energy           | 🔴                   |
</div>

## Section 5.3: Temporal Circularity Profile
### Figure 5: Temporal Circularity Profile
<div align="center">
```mermaid
graph TD;
    A[t=1: 0.85] -->|Dark Red| B[t=2: 0.70]
    B -->|Dark Red| C[t=3: 0.60]
    C -->|Dark Red| D[t=4: 0.50]
    D -->|Dark Red| E[t=5: 0.40]
    E -->|Dark Red| F[t=6: 0.30]
    F -->|Dark Red| G[t=7: 0.20]
    G -->|Dark Red| H[t=8: 0.10]
    H -->|Dark Red| I[t=9: 0.05]
    I -->|Nearly White| J[t=10: 0.01]
```
</div>

