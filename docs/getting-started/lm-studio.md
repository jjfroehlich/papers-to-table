# Model Provider (LM Studio)

papers-to-table uses large language models and needs a LLM provider, currently it works with LM Studio.


## Install LM Studio

1. Download LM Studio from the [official downloads page](https://lmstudio.ai/download).
2. Install it for your operating system (Windows, macOS, or Linux).
3. Open LM Studio and confirm it can browse/search models.


## Download A Model

Download a model in LM Studio.

The current default suggested model:

```text
google/gemma-4-e4b
```

If you choose a different model, update `provider.text_model.model_id` in `app/config.json` so the app and LM Studio agree.

See [Model Choice](model-choice.md) for benchmark-based guidance on quality and runtime trade-offs.

## Start The Local Server

Start LM Studio's local developer server and keep it running while using papers-to-table. 

The local endpoint should automatically be available at:

```text
http://localhost:1234
```

## Expected Provider Values

- provider token: `lm_studio`
- default base URL: `http://localhost:1234`
- default text model: `google/gemma-4-e4b`
- provider must be reachable before extraction starts
- configured model must be available in LM Studio
