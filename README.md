# Paper-table-agent

Paper-table-agent is an experimental local-first pipeline to extract and organize information from research papers using large language models. 

## How to use it
Input: 
 - a .xlsx table with one row per paper, columns Title/Authors/Year and a column for each of the desired information. Optional: an extra tab with a brief description of what each column should capture, this can also contain examples of filled cells (to clarify if a column captures numbers, short strings, or longer text/argumentation). 
 - a folder with .pdf files of papers. 
 
 The app first matches .pdfs to rows, then extracts values for each cell, and lets you review each proposed value in a minimal Run/Review UI together with reasoning and evidence display.

## Installation

1. Clone the repo:
```bash
git clone https://github.com/jjfroehlich/paper-table-agent
cd paper-table-agent
```
2. 
```bash
[TODO: to be completed in the future]
```

You also need LM Studio, models specialized in embedding (e.g. text-embedding-nomic-embed-text-v1.5, text-embedding-bge-small-en-v1.5), and a capable model for extraction and reasoning (e.g. qwen/qwen3-30b-a3b-2507). You might also need a model with vision capabilities to extract information from figures. Optional: LM Studio can also be connected to more capable cloud-based models (e.g. Gemini Pro 3, GPT-5.2) with API keys.

## Quickstart
```bash
[TODO: to be completed in the future]
```

## How it works technically

### Pipeline flow

[TODO: to be completed in the future]

### Evidence + review

[TODO: to be completed in the future]

## Config (single source of truth)

[TODO: to be completed in the future]


## Repo structure (short)

[TODO: to be completed in the future]
