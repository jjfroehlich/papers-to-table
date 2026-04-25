DEFAULT_MODEL_ID = 'unsloth/gemma-4-26b-a4b-it'
CANONICAL_PROVIDERS = {'lm_studio'}
PROVIDER_DISPLAY_NAMES = {'lm_studio': 'LM Studio'}
CANONICAL_RETRIEVAL_MODES = {'lexical', 'hybrid_experimental'}
LEGACY_RETRIEVAL_MODE_ALIASES = {
    'semantic_chunks': 'lexical',
    'baseline': 'lexical',
    'hybrid': 'hybrid_experimental',
}
