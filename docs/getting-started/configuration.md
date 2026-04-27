# Configuration

The main app uses JSON as the advanced-control authority.

- Canonical template: `app/config.example.json`
- Local working config: `app/config.json`

Required top-level fields:

- `table_path`
- `schema_path`
- `pdf_dir`
- `output_dir`
- `provider.token`
- `provider.text_model.model_id`

Default live provider path is LM Studio (`provider.token = "lm_studio"`).

For full field-level guidance and companion-tool config surfaces, see the detailed reference: [`../configuration.md`](../configuration.md).
