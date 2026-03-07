# MINERVA Baseline Architecture
[cite_start]**Project:** Microbiomes Network for Research and Visualization Atlas (SanoMap)[cite: 157].
[cite_start]**Objective:** Map associations between gut microbes and systemic diseases using text-mining[cite: 157].

# Github for the orignal research codebase: https://github.com/MGH-LMIC/MINERVA

## Core Pipeline
1. [cite_start]**Named Entity Recognition (NER):** - Utilizes SciBERT and DistilBERT models for microbial and disease extraction[cite: 175].
   - [cite_start]Maps the endpoints of microbes to diseases[cite: 159].
2. **Knowledge Graph (Neo4j):**
   - [cite_start]Data is structured into a Neo4j graph[cite: 168].
   - [cite_start]Resolves inter-paper conflicts using an established heuristic that incorporates the impact factor of the published journal[cite: 186].