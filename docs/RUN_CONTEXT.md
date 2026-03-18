# Run Context

Read this file at the start of implementation work.

## Runtime Ownership
- Shared project truth lives in:
  - `AGENTS.md`
  - `docs/*.md`
  - `pipeline_tracking.md`
- Repo-local runtime files are:
  - `.claude/settings.json`
  - `.codex/config.toml`
- Cursor is an editor surface, not a third repo-local runtime target.

## Publication Boundary
- This GitHub repository is the supervisor-visible production work surface for the internship.
- Safe to commit:
  - shared project docs
  - reusable repo-local runtime files
  - code, tests, and research/reference artifacts intended for team review
- Keep local only:
  - `sample_papers/`
  - `.claude/settings.local.json`
  - user auth state
  - trust settings in home-directory tool configs
  - `.env*`
  - `secrets/`
  - private keys or machine-specific overrides

## Local Python Runtime Policy
- Local Python-backed repo automation and `agent-os` helper work run in Conda `base`.
- Homebrew Python is not the supported runtime for repo-local helper automation.
- Unless a remote or hosted environment is explicitly documented for a run, local helper commands should assume Conda `base`.

## Execution Profiles
### `local_mac_base`
- Hardware:
  - Apple M2
  - `8 GB` unified memory
  - `arm64`
  - `MPS` available
- Valid use:
  - orchestration
  - smoke tests
  - text-stage artifact rebuilds
  - audits and validation
  - query exploration loops
  - light model-selection experiments
- Not valid as the default path for:
  - final model-backed merged relation production
  - heavy local relation extraction runs meant to approximate upstream execution

### `remote_gpu_tbd`
- This is the preferred production profile for real model-backed merged relation extraction.
- The exact host, scheduler, and access pattern are still undecided.
- When used, record:
  - backend
  - model id
  - device
  - runtime
  - artifact outputs
  - any environment-specific rate or quota constraints

### `hosted_inference_tbd`
- This is the fallback production profile if a remote GPU environment is not used.
- Before relying on it, record:
  - provider
  - model id
  - cost assumptions
  - rate limits
  - retry policy
- Hosted inference is still non-local production; do not treat it as interchangeable with `local_mac_base`.
- The relation stage can now use `--backend openai_compatible` against providers that expose a chat-completions-compatible API.
- Hugging Face router is the first intended hosted target:
  - `https://router.huggingface.co/v1`
- Keep provider credentials in local environment variables only.
- First hosted smoke result on 2026-03-18:
  - sourcing the sibling local `.env` file succeeded
  - Hugging Face router returned `model_not_supported` for `BioMistral/BioMistral-7B` on the current account/provider setup
  - `deepseek-ai/DeepSeek-V3-0324` completed a 3-row smoke run successfully through the same backend path
- Provider-routing findings from the 2026-03-18 pilot:
  - HF router auto-routed `meta-llama/Llama-3.1-8B-Instruct` to Cerebras in this environment, and Cerebras returned Cloudflare `1010` access denied
  - HF router auto-routed `Qwen/Qwen2.5-7B-Instruct` to Together in this environment, and Together returned Cloudflare `1010` access denied
  - HF router accepted explicit provider suffixes in model ids, but `meta-llama/Llama-3.1-8B-Instruct:novita` then failed with `402` because included HF credits were exhausted
  - `deepseek-ai/DeepSeek-V3-0324` remains the only confirmed HF-router model/provider path that actually completed in this environment

## API And Rate-Limit Policy
- No hosted provider or remote quota policy is locked yet.
- When a hosted or remote execution path is chosen, document its limits here before large runs.
- Current relation-stage environment variable support:
  - base URL: `RELATION_API_BASE_URL` or `OPENAI_BASE_URL`
  - API key: `RELATION_API_KEY`, `HUGGINGFACE_API_KEY`, `HF_TOKEN`, or `OPENAI_API_KEY`
- Gemini-specific relation-stage support now exists:
  - base URL override: `GEMINI_API_BASE_URL`
  - API key override: `GEMINI_API_KEY`
  - if the model id starts with `gemini-`, the relation stage now defaults to Google's official OpenAI-compatible base URL:
    - `https://generativelanguage.googleapis.com/v1beta/openai`
- The relation backend is intentionally generic enough that Ollama or another OpenAI-compatible provider can later reuse the same interface.
- For the current Hugging Face account, treat model availability as an account/provider capability question rather than a code-path question.
- Treat HF included credits as effectively exhausted for further model-comparison work unless the account is upgraded, topped up, or replaced by a direct provider key.
- Gemini-provider guardrail:
  - if a `gemini-*` model is accidentally pointed at a non-Google base URL, the backend now fails fast with a provider-mismatch error instead of sending the request to the wrong provider

## Model Availability Note
- Some model weights and checkpoints used in or associated with the upstream MINERVA paper are not yet available in this workspace.
- Because of that, this repository currently uses default substitute models to get a proof-of-concept end-to-end pipeline running first.
- This is intentional. The immediate goal is pipeline completion and evidence flow validation, not final model parity.
- Professor-mediated review is the current likely path if any upstream or private checkpoints become available for inspection or reruns.
- If that handoff happens, document the model ids, access assumptions, and execution steps in repo docs, but do not commit restricted weights or private access material into Git.

## Current Substitute Model Policy
- Relation extraction targets `BioMistral/BioMistral-7B` when model-backed text generation is available.
- Data augmentation currently uses `mistralai/Mixtral-8x7B-v0.1`.
- Microbe NER currently uses `d4data/biomedical-ner-all`.
- Disease NER currently uses `allenai/scibert_scivocab_uncased` with fallback to `en_ner_bc5cdr_md`.
- Vision proposal currently uses `Qwen/Qwen2.5-VL-7B-Instruct`.

## Current Workspace Constraint
- This workspace is currently CPU-only (`cuda_available = false`) for practical relation-production purposes.
- For merged proof-of-concept relation extraction runs in this workspace, `BioMistral/BioMistral-7B` text generation is not a practical default execution path.
- Model-backed merged relation production is non-local by default.
- When that constraint matters, record explicitly whether the run used the intended text-generation backend or the `heuristic` backend.
- The 2026-03-17 local merged rebuild also ran in an offline/no-network environment for Hugging Face model fetches:
  - `d4data/biomedical-ner-all` could not be downloaded
  - `src/text_ner_minerva.py` therefore reported `microbe_model_available = false`
  - the local rebuild used regex fallback for microbe extraction, so recall should not be compared directly to a cached-model or remote run

## Interim Candidate Models
- If microbe NER quality is the priority, evaluate `pruas/BENT-PubMedBERT-NER-Organism`.
- If microbe NER speed is the priority, evaluate `OpenMed/OpenMed-NER-SpeciesDetect-ElectraMed-33M`.
- If disease NER coverage is the priority, evaluate `pruas/BENT-PubMedBERT-NER-Disease`.
- If disease NER should stay BC5CDR-oriented, evaluate `Francesco-A/BiomedNLP-PubMedBERT-base-uncased-abstract-bc5cdr-ner-v1`.
- Do not switch relation extraction or vision defaults just because they are newer. The current bottleneck is the text NER stage.

## Why This Matters
- Do not describe the current model stack as exact upstream parity.
- Describe it as a proof-of-concept substitute stack aligned with upstream methodology.
- When the intended upstream weights/checkpoints become available, the pipeline should be re-run with those models and re-evaluated.

## Query Assessment Snapshot
- The split query design is correct for the current hybrid scope.
- `microbe_radiomics_strict`, `microbe_imaging_adjacent`, and `microbe_bodycomp` are appropriately separated.
- Keep `microbe_radiomics_strict` as the explicit-radiomics precision lane.
- Use `microbe_imaging_adjacent` for adjacent imaging phenotype papers that do not say `radiomics`.
- The current merged microbe-side corpus is mostly imaging phenotype/body-composition, not mostly strict radiomics.
- The main current limitation is that the disease-side queries are more tuned to predictive/prognostic language than to general association language.
- For proof of concept, keep the current queries stable unless recall becomes a blocker.

## NER Optimization Snapshot
- Prefer batching and inference reduction before large model swaps.
- `src/text_ner_minerva.py` now chunks long sentences, batches NER calls, and runs microbe NER only after disease-positive sentence filtering.
- Revisit model substitution only after checking whether those safer runtime optimizations are enough.
