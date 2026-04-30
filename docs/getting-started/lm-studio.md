# Model Provider (LM Studio)

papers-to-table uses large language models and needs a LLM provider, currently it works with LM Studio.


## Install LM Studio

You need to set up LM Studio before installing and running the app, it is available for Windows, macOS, and Linux.

1. Download LM Studio from the [official downloads page](https://lmstudio.ai/download).
2. Install it for your operating system.
3. Open LM Studio and confirm it can browse/search models.


## Download A Model

Download a model in LM Studio before starting papers-to-table.

The current default model documented by this repo is:

```text
unsloth/gemma-4-26b-a4b-it
```

If you choose a different model, update `provider.text_model.model_id` in `app/config.json` so the app and LM Studio agree.

## Start The Local Server

Start LM Studio's local developer server and keep it running while using papers-to-table. 

The local endpoint should automatically be available at:

```text
http://localhost:1234
```

The app expects an LM Studio/OpenAI-compatible local API at that base URL unless you configure a different `provider.base_url`.

## Expected Provider Values

- provider token: `lm_studio`
- default base URL: `http://localhost:1234`
- default text model: `unsloth/gemma-4-26b-a4b-it`
- provider must be reachable before extraction starts
- configured model must be available in LM Studio
